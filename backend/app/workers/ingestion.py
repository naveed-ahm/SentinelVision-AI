"""Video ingestion + AI worker.

Owns every long-running loop (video capture, detection, ANPR, tracking).
Deliberately isolated from API request handlers so they never block on video
or inference. Run standalone with: python -m app.workers.ingestion
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

import cv2
import numpy as np

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.ai_modules import AnomalyReview, PersonDetection, QualityMetric, ReidMatch, VehicleAttribute
from app.models.camera import Camera
from app.models.event import DetectionEvent, PlateRead, Vehicle, VehicleSighting
from app.models.user import utcnow
from app.services import camera_service
from app.services.alert_service import events_bus, raise_alert
from app.services.detection_service import detector, plate_reader
from app.services.storage import storage
from app.services.tracking_service import IoUTracker
from app.workers.live_store import live_store
from app.workers.spooler import FrameEntry, spooler

logger = logging.getLogger("sentinelvision.ingest")

COLORS = [(37, 99, 235), (22, 163, 74), (245, 158, 11), (220, 38, 38), (147, 51, 234), (8, 145, 178)]


def _jpeg_encode(frame: np.ndarray, quality: int = 70) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""


def _annotate(frame: np.ndarray, tracks: list) -> np.ndarray:
    out = frame.copy()
    for i, t in enumerate(tracks):
        x, y, w, h = (int(v) for v in t.bbox)
        color = COLORS[i % len(COLORS)]
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
        plate = t.confirmed_plate or (t.extras.get("plate_text") if hasattr(t, "extras") and t.extras.get("plate_text") else "")
        label = f"{t.label} {t.confidence:.2f}" + (f" | {plate}" if plate else "")
        ty = max(y - 8, 14)
        cv2.putText(out, label, (x, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (10, 12, 18), 3)
        cv2.putText(out, label, (x, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 248, 255), 1)
    return out


class CameraWorker(threading.Thread):
    """One video source: decode -> sample -> detect -> track -> persist."""

    def __init__(self, camera: Camera) -> None:
        super().__init__(daemon=True, name=f"cam-{camera.code}")
        self.camera = camera
        self.stop_event = threading.Event()
        self.tracker = IoUTracker()
        self.seq = 0
        self._last_frame: np.ndarray | None = None
        self._last_persisted_track: dict[int, float] = {}

    def _resolve_source(self) -> str | int:
        cam = self.camera
        if cam.protocol == "webcam":
            return 0
        return camera_service.build_effective_url(cam)

    def _update_status(self, status: str, error: str = "") -> None:
        db = SessionLocal()
        try:
            cam = db.get(Camera, self.camera.id)
            if cam:
                cam.status = status
                cam.last_error = error[:500]
                if status == "online":
                    cam.last_connected_at = utcnow()
                cam.last_health_check = utcnow()
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _persist_detection(self, track, ts: datetime) -> None:
        """Persist a detection event, throttled per track to avoid flooding."""
        last = self._last_persisted_track.get(track.track_id, 0.0)
        if time.monotonic() - last < 2.0:  # one stored event per track per 2s
            return
        self._last_persisted_track[track.track_id] = time.monotonic()

        db = SessionLocal()
        plate_read_id = None
        plate_text = ""
        plate_conf = 0.0
        vehicle_crop_bgr = None  # kept for the optional attribute/Re-ID modules
        try:
            cam = db.get(Camera, self.camera.id)
            if cam is None:
                return

            image_path = ""
            if self._last_frame is not None:
                x, y, w, h = (int(v) for v in track.bbox)
                H, W = self._last_frame.shape[:2]
                crop = self._last_frame[max(y, 0):min(y + h, H), max(x, 0):min(x + w, W)]
                if crop.size > 0:
                    vehicle_crop_bgr = crop  # reused by the optional attribute/Re-ID modules
                    ok, enc = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ok:
                        image_path = storage.save_jpeg(
                            enc.tobytes(),
                            f"{cam.code}/detections",
                            f"{track.label}_{int(ts.timestamp())}_{track.track_id}",
                        )

            event = DetectionEvent(
                camera_id=self.camera.id,
                timestamp=ts,
                object_class=track.label,
                confidence=round(track.confidence, 4),
                bbox_x=track.bbox[0],
                bbox_y=track.bbox[1],
                bbox_w=track.bbox[2],
                bbox_h=track.bbox[3],
                track_id=track.track_id,
                image_path=image_path,
                is_demo=cam.is_demo,
            )

            # ANPR: attempt a plate read on the vehicle bbox.
            if track.label != "person":
                crop = plate_reader.propose_plate_crop(self._last_frame, track.bbox) if self._last_frame is not None else None
                if crop is not None and crop.size > 0:
                    text, conf = plate_reader.read_text(crop)
                    if text or conf > 0:
                        needs_review = (not plate_reader.is_plausible(text)) or conf < settings.OCR_MIN_CONFIDENCE
                        crop_path = ""
                        if text:
                            ok2, enc2 = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            if ok2:
                                crop_path = storage.save_jpeg(
                                    enc2.tobytes(),
                                    f"{cam.code}/plates",
                                    f"plate_{int(ts.timestamp())}_{track.track_id}",
                                )
                        pr = PlateRead(
                            plate_text=text[:20],
                            raw_text=text[:40],
                            ocr_confidence=round(conf, 4),
                            needs_review=needs_review,
                            crop_path=crop_path,
                            is_demo=cam.is_demo,
                        )
                        db.add(pr)
                        db.flush()
                        plate_read_id = pr.id
                        plate_text, plate_conf = text, conf
                        if needs_review and text:
                            raise_alert(
                                db,
                                "unreadable_plate",
                                f"Unreadable plate on {cam.name}",
                                f"OCR returned '{text}' (conf {conf:.2f}); manual review required.",
                                severity="info",
                                camera_id=cam.id,
                                is_demo=cam.is_demo,
                            )

            event.plate_read_id = plate_read_id
            db.add(event)
            db.flush()

            # ---------- Optional module: vehicle attribute recognition ----------
            # Stored separately in vehicle_attributes; any failure is swallowed.
            try:
                if settings.ENABLE_ATTRIBUTES and vehicle_crop_bgr is not None and track.label != "person":
                    from app.services.attributes_service import attribute_recognizer

                    attrs = attribute_recognizer.recognize(vehicle_crop_bgr, yolo_label=track.label)
                    if attrs:
                        db.add(
                            VehicleAttribute(
                                event_id=event.id,
                                camera_id=self.camera.id,
                                timestamp=ts,
                                vehicle_type=attrs.get("vehicle_type", "")[:24],
                                color=attrs.get("color", "")[:24],
                                color_confidence=attrs.get("color_confidence", 0.0),
                                body_style=attrs.get("body_style", "")[:24],
                                attributes=attrs,
                                model_name=attrs.get("model_name", "")[:64],
                                is_demo=cam.is_demo,
                            )
                        )
                        db.flush()
            except Exception as exc:
                logger.debug("attributes module skipped: %s", exc)

            # ---------- Optional module: vehicle Re-ID (unconfirmed matches) ----------
            try:
                if settings.ENABLE_REID and vehicle_crop_bgr is not None and track.label != "person":
                    from app.services.reid_service import reid_engine

                    match = reid_engine.register_and_match(
                        event_id=event.id,
                        camera_id=self.camera.id,
                        crop_bgr=vehicle_crop_bgr,
                        label=track.label,
                        color="",
                        confirmed_plate=plate_text if (plate_text and plate_conf >= settings.OCR_MIN_CONFIDENCE and plate_reader.is_plausible(plate_text)) else "",
                        is_demo=cam.is_demo,
                    )
                    if match:
                        db.add(
                            ReidMatch(
                                event_id=event.id,
                                camera_id=self.camera.id,
                                matched_event_id=match.get("matched_event_id"),
                                matched_camera_id=match.get("matched_camera_id"),
                                similarity=match.get("similarity", 0.0),
                                matched_plate=(match.get("matched_plate") or "")[:20],
                                status="confirmed" if match.get("confirmed_by_plate") else "unconfirmed",
                                is_demo=cam.is_demo,
                            )
                        )
                        db.flush()
                        events_bus.publish_now(
                            {
                                "type": "reid_match",
                                "match": {
                                    "camera_id": self.camera.id,
                                    "camera_name": cam.name,
                                    "similarity": match.get("similarity"),
                                    "matched_plate": match.get("matched_plate") or None,
                                    "status": "confirmed" if match.get("confirmed_by_plate") else "unconfirmed",
                                    "timestamp": ts.isoformat(),
                                    "is_demo": cam.is_demo,
                                },
                            }
                        )
            except Exception as exc:
                logger.debug("reid module skipped: %s", exc)

            # Confirmed plate -> vehicle identity + sighting
            if plate_text and plate_conf >= settings.OCR_MIN_CONFIDENCE and plate_reader.is_plausible(plate_text):
                vehicle = db.query(Vehicle).filter(Vehicle.registration_number == plate_text).first()
                if not vehicle:
                    vehicle = Vehicle(registration_number=plate_text, vehicle_class=track.label, is_demo=cam.is_demo)
                    db.add(vehicle)
                    db.flush()
                vehicle.last_seen_at = ts
                vehicle.total_sightings += 1
                db.add(VehicleSighting(vehicle_id=vehicle.id, event_id=event.id, camera_id=self.camera.id, timestamp=ts))

                # ---------- Optional module: watchlist matching ----------
                # Runs after the confirmed-plate identity path; any failure is
                # swallowed and cannot affect the existing persistence flow.
                try:
                    if settings.ENABLE_WATCHLIST:
                        from app.services.watchlist_service import watchlist_service

                        watchlist_service.check_plate(
                            db,
                            plate_text=plate_text,
                            ocr_confidence=plate_conf,
                            plate_read_id=plate_read_id,
                            event_id=event.id,
                            camera_id=self.camera.id,
                            evidence_path=image_path,
                            is_demo=cam.is_demo,
                            camera_name=cam.name,
                        )
                except Exception as exc:
                    logger.debug("watchlist module skipped: %s", exc)

                if vehicle.total_sightings % 10 == 0:
                    raise_alert(
                        db,
                        "repeated_vehicle",
                        f"Vehicle {plate_text} reached {vehicle.total_sightings} sightings",
                        f"Seen again on {cam.name} ({cam.location_name}).",
                        severity="info",
                        camera_id=cam.id,
                        event_id=event.id,
                        is_demo=cam.is_demo,
                    )

            db.commit()
            events_bus.publish_now(
                {
                    "type": "detection",
                    "detection": {
                        "camera_id": self.camera.id,
                        "camera_name": cam.name,
                        "object_class": track.label,
                        "confidence": round(track.confidence, 3),
                        "plate_text": plate_text or None,
                        "timestamp": ts.isoformat(),
                        "is_demo": cam.is_demo,
                    },
                }
            )
            # remember for the optional anomaly module (not a persisted column)
            track._last_event_id = event.id
        except Exception as exc:
            db.rollback()
            logger.warning("persist failed for %s: %s", self.camera.code, exc)
        finally:
            db.close()

    def _persist_persons(self, ts: datetime, persons: list[dict]) -> None:
        """Optional person-model rows (presence only; no identity inference)."""
        db = SessionLocal()
        try:
            cam = db.get(Camera, self.camera.id)
            if cam is None or not persons:
                return
            for p in persons[:20]:  # safety cap per frame
                x, y, w, h = p["bbox"]
                db.add(
                    PersonDetection(
                        camera_id=self.camera.id,
                        timestamp=ts,
                        confidence=round(p["confidence"], 4),
                        bbox_x=x, bbox_y=y, bbox_w=w, bbox_h=h,
                        is_demo=cam.is_demo,
                    )
                )
            db.commit()
            events_bus.publish_now(
                {
                    "type": "person_detection",
                    "person_detection": {
                        "camera_id": self.camera.id,
                        "camera_name": cam.name,
                        "count": len(persons),
                        "max_confidence": round(max(p["confidence"] for p in persons), 3),
                        "timestamp": ts.isoformat(),
                        "is_demo": cam.is_demo,
                    },
                }
            )
        except Exception as exc:
            db.rollback()
            logger.debug("person persist skipped: %s", exc)
        finally:
            db.close()

    def _persist_quality(self, frame: np.ndarray, ts: datetime) -> None:
        """Optional quality score for one sampled frame; purely informational."""
        try:
            from app.services.quality_service import quality_assessor

            result = quality_assessor.assess(frame)
            if result is None:
                return
            db = SessionLocal()
            try:
                cam = db.get(Camera, self.camera.id)
                if cam is None:
                    return
                db.add(
                    QualityMetric(
                        camera_id=self.camera.id,
                        timestamp=ts,
                        composite=result["composite"],
                        blur_score=result["blur_score"],
                        brightness_score=result["brightness_score"],
                        visibility_score=result["visibility_score"],
                        verdict=result["verdict"],
                        is_demo=cam.is_demo,
                    )
                )
                db.commit()
                if result["verdict"] == "poor":
                    events_bus.publish_now(
                        {
                            "type": "quality",
                            "quality": {
                                "camera_id": self.camera.id,
                                "camera_name": cam.name,
                                "composite": result["composite"],
                                "verdict": result["verdict"],
                                "timestamp": ts.isoformat(),
                            },
                        }
                    )
            finally:
                db.close()
        except Exception as exc:
            logger.debug("quality module skipped: %s", exc)

    def _handle_anomaly_finding(self, ts: datetime, finding: dict, track) -> None:
        """Optional anomaly review event (severity info; never a criminal label)."""
        try:
            from app.services.anomaly_service import anomaly_engine

            db = SessionLocal()
            try:
                cam = db.get(Camera, self.camera.id)
                if cam is None:
                    return
                review = AnomalyReview(
                    camera_id=self.camera.id,
                    event_id=getattr(track, "_last_event_id", None),
                    timestamp=ts,
                    anomaly_type=finding.get("anomaly_type", "speed")[:32],
                    score=finding.get("score", 0.0),
                    detail=finding.get("detail", "")[:255],
                    review_status="pending",
                    is_demo=cam.is_demo,
                )
                db.add(review)
                db.commit()
                raise_alert(
                    db,
                    "anomaly_review",
                    f"Movement review suggested on {cam.name}",
                    f"{finding.get('detail', '')} (Appearance/motion heuristic — human review required, "
                    "not an automated classification.)",
                    severity="info",
                    camera_id=cam.id,
                    is_demo=cam.is_demo,
                )
            finally:
                db.close()
        except Exception as exc:
            logger.debug("anomaly module skipped: %s", exc)

    def run(self) -> None:
        logger.info("worker start: %s (%s)", self.camera.code, self.camera.protocol)
        retry_delay = 2.0
        frame_interval = 1.0 / max(settings.INGEST_FPS_LIMIT, 1.0)
        detect_every = max(int(settings.DETECTION_SAMPLE_INTERVAL * max(settings.INGEST_FPS_LIMIT, 1.0)), 1)

        while not self.stop_event.is_set():
            source = self._resolve_source()
            if source in ("", None):
                self._update_status("error", "No source URL configured")
                time.sleep(5)
                continue

            cap = (
                cv2.VideoCapture(source, cv2.CAP_FFMPEG)
                if self.camera.protocol == "rtsp"
                else cv2.VideoCapture(source)
            )
            if not cap.isOpened():
                self._update_status("error", "Cannot open source")
                events_bus.publish_now({"type": "camera_status", "camera_id": self.camera.id, "status": "error"})
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 30)
                continue

            retry_delay = 2.0
            self._update_status("online")
            events_bus.publish_now({"type": "camera_status", "camera_id": self.camera.id, "status": "online"})
            frame_idx = 0

            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    if self.camera.protocol == "file":
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop demo file
                        continue
                    break  # RTSP hiccup -> reconnect

                now = time.monotonic()
                self._last_frame = frame
                self.seq += 1
                frame_idx += 1

                tracks: list = []
                if self.camera.detection_enabled and detector.available and frame_idx % detect_every == 0:
                    raw = detector.detect(frame)
                    ts_now = datetime.now(timezone.utc)
                    tracks = self.tracker.update(raw, ts_now.timestamp())
                    for t in tracks:
                        if t.misses == 0 and t.hits >= 2:
                            self._persist_detection(t, ts_now)
                            # Optional module: unusual-movement review events.
                            # Independent of the persistence path above; failures are swallowed.
                            try:
                                if settings.ENABLE_ANOMALY:
                                    from app.services.anomaly_service import anomaly_engine

                                    finding = anomaly_engine.evaluate_track(
                                        camera_id=self.camera.id,
                                        track_id=t.track_id,
                                        label=t.label,
                                        history=t.history,
                                        sample_interval=settings.DETECTION_SAMPLE_INTERVAL,
                                    )
                                    if finding:
                                        self._handle_anomaly_finding(ts_now, finding, t)
                            except Exception as exc:
                                logger.debug("anomaly module skipped: %s", exc)

                # Optional module: dedicated person model (fully independent of the
                # vehicle YOLO service above — own instance, own flag, own try/except).
                try:
                    if (
                        self.camera.detection_enabled
                        and settings.ENABLE_PERSON_MODEL
                        and frame_idx % detect_every == 0
                    ):
                        from app.services.person_service import person_detector

                        if person_detector.available or person_detector.load():
                            persons = person_detector.detect(frame)
                            if persons:
                                ts_now2 = datetime.now(timezone.utc)
                                self._persist_persons(ts_now2, persons)
                except Exception as exc:
                    logger.debug("person module skipped: %s", exc)

                # Optional module: frame quality sampling (pure cv2; informational only).
                try:
                    if settings.ENABLE_QUALITY and frame_idx % max(settings.QUALITY_SAMPLE_EVERY_N, 1) == 0:
                        from app.services.quality_service import quality_assessor

                        if quality_assessor.available or quality_assessor.load():
                            self._persist_quality(frame, datetime.now(timezone.utc))
                except Exception as exc:
                    logger.debug("quality module skipped: %s", exc)

                annotated = _annotate(frame, tracks) if tracks else frame
                jpeg = _jpeg_encode(frame)
                ajpeg = _jpeg_encode(annotated) if tracks else jpeg
                if ajpeg:
                    spooler.push(self.camera.id, FrameEntry(seq=self.seq, jpeg=jpeg, annotated_jpeg=ajpeg, ts=time.time()))
                    # publish for the API process (cross-process live view)
                    try:
                        live_store.publish(self.camera.code, self.seq, ajpeg)
                    except Exception:
                        pass

                elapsed = time.monotonic() - now
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)

            cap.release()
            if not self.stop_event.is_set():
                self._update_status("error", "Stream interrupted")
                events_bus.publish_now({"type": "camera_status", "camera_id": self.camera.id, "status": "offline"})
                time.sleep(retry_delay)


class IngestionManager:
    """Syncs CameraWorkers with the camera table every few seconds."""

    def __init__(self) -> None:
        self._workers: dict[int, CameraWorker] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._supervise, daemon=True, name="ingestion-manager")
        self._thread.start()
        spooler.running = True

    def stop(self) -> None:
        self._stop.set()
        spooler.running = False
        with self._lock:
            for w in self._workers.values():
                w.stop_event.set()

    def _supervise(self) -> None:
        while not self._stop.is_set():
            db = SessionLocal()
            try:
                cams = (
                    db.query(Camera)
                    .filter(Camera.enabled.is_(True))
                    .limit(settings.MAX_CONCURRENT_STREAMS)
                    .all()
                )
                wanted = {c.id for c in cams}
                for cam in cams:
                    _ = cam.credential  # force-load now: worker threads outlive this session
                with self._lock:
                    for cid in list(self._workers):
                        if cid not in wanted:
                            self._workers[cid].stop_event.set()
                            del self._workers[cid]
                            spooler.clear_camera(cid)
                    for cam in cams:
                        if cam.id not in self._workers:
                            w = CameraWorker(cam)
                            self._workers[cam.id] = w
                            w.start()
            finally:
                db.close()
            self._stop.wait(5.0)

    @property
    def camera_states(self) -> dict:
        with self._lock:
            return {cid: w.camera.code for cid, w in self._workers.items()}


manager = IngestionManager()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logger.info("Starting SentinelVision ingestion worker (Ctrl+C to stop)")
    manager.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop()
