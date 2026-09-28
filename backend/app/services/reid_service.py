"""Vehicle Re-identification module (optional, independent).

Extracts appearance fingerprints (color histogram / optional embedding model)
from vehicle crops, keeps a small in-memory gallery of recent sightings, and
records candidate cross-camera matches in the new ``reid_matches`` table.

POLICY (mirrors the platform's existing stance): appearance similarity is a
*lead*, never identity. Matches are always stored with
``status = "unconfirmed"`` unless a confirmed ANPR plate read binds both sides.
The platform's existing ``correlate_sightings`` (plate-confirmed-only) is not
modified; this module adds a separate, parallel signal.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from app.core.config import settings

logger = logging.getLogger("sentinelvision.ai.reid")


@dataclass
class AppearanceFingerprint:
    """One vehicle appearance observation kept in the in-memory gallery."""

    event_id: int
    camera_id: int
    vehicle_label: str
    color: str
    vector: list[float]
    plate: str  # confirmed plate at observation time, "" when unknown
    ts: float
    is_demo: bool = False
    source: str = "heuristic"  # heuristic | embedding


class ReidEngine:
    """Singleton gallery + cosine similarity matcher (lazy, thread-safe)."""

    def __init__(self) -> None:
        self._gallery: list[AppearanceFingerprint] = []
        self._lock = threading.Lock()
        self.available = False
        self.load_error = ""
        self._embedder = None  # optional torch tier, loaded lazily

    def load(self) -> bool:
        if self.available:
            return True
        try:
            self.available = True  # heuristic tier needs only numpy/cv2
            logger.info("Re-ID engine ready (heuristic tier)")
        except Exception as exc:
            self.load_error = str(exc)[:300]
            logger.warning("Re-ID unavailable: %s", self.load_error)
        return self.available

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        try:
            va = np.asarray(a, dtype=np.float32)
            vb = np.asarray(b, dtype=np.float32)
            denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
            return float(va @ vb / denom) if denom > 0 else 0.0
        except Exception:
            return 0.0

    def register_and_match(
        self,
        *,
        event_id: int,
        camera_id: int,
        crop_bgr: np.ndarray,
        label: str,
        color: str = "",
        confirmed_plate: str = "",
        is_demo: bool = False,
    ) -> dict | None:
        """Add this observation to the gallery and return the best prior match.

        Returns ``None`` when the module is disabled/unavailable, the crop is
        unusable, or no gallery entry clears the similarity threshold. Never
        raises into the worker.
        """
        if not settings.ENABLE_REID or not self.load():
            return None
        try:
            vector, source = None, "heuristic"
            if self._embedder is not None:
                vector = self._embedder.embed(crop_bgr)
                source = "embedding"
            if vector is None:
                from app.services._embedding_model import heuristic_embedding

                vector = heuristic_embedding(crop_bgr)
            if not vector:
                return None

            now = time.time()
            best: tuple[float, AppearanceFingerprint] | None = None
            with self._lock:
                ttl = settings.REID_MATCH_TTL_MINUTES * 60
                for fp in self._gallery:
                    if fp.camera_id == camera_id:
                        continue  # cross-camera by definition
                    if now - fp.ts > ttl:
                        continue
                    sim = self.cosine(vector, fp.vector)
                    if sim >= settings.REID_SIMILARITY_THRESHOLD and (best is None or sim > best[0]):
                        best = (sim, fp)

                # conservative gallery trimming
                self._gallery = [
                    fp for fp in self._gallery if now - fp.ts <= ttl
                ][-settings.REID_HISTORY_SIZE:]
                self._gallery.append(
                    AppearanceFingerprint(
                        event_id=event_id,
                        camera_id=camera_id,
                        vehicle_label=label,
                        color=color,
                        vector=vector,
                        plate=confirmed_plate,
                        ts=now,
                        is_demo=is_demo,
                        source=source,
                    )
                )

            if best is None:
                return None
            sim, fp = best
            return {
                "matched_event_id": fp.event_id,
                "matched_camera_id": fp.camera_id,
                "similarity": round(sim, 4),
                "matched_plate": fp.plate,
                "confirmed_by_plate": bool(confirmed_plate and fp.plate and confirmed_plate == fp.plate),
                "source": source,
            }
        except Exception as exc:
            logger.warning("reid register/match failed: %s", exc)
            return None

    def set_embedder(self, embedder) -> None:
        """Attach the optional torch embedding tier (no-op if unavailable)."""
        self._embedder = embedder

    def gallery_size(self) -> int:
        with self._lock:
            return len(self._gallery)

    def reset(self) -> None:
        with self._lock:
            self._gallery.clear()


reid_engine = ReidEngine()
