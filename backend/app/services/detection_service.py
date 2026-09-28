"""AI detection services: YOLO object detection and ANPR (plate OCR).

Both components degrade gracefully: when the optional heavy dependencies
(ultralytics / paddleocr) are not installed, the services report
``available = False`` and the platform keeps running in degraded mode with
a clear banner in the UI. No fake detections are ever produced.
"""
import logging
import os
import re
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.core.config import settings

logger = logging.getLogger("sentinelvision.ai")

# COCO class ids of interest
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
PERSON_CLASS = 0
PERSON_LABEL = "person"

# Indian registration plate format (loose): 2 letters + 1-2 digits + up to 3
# letters/1-4 digits tail. Used only to flag implausible OCR output.
PLATE_RE = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}$")
_PLATE_STRIP_RE = re.compile(r"[^A-Z0-9]+")


@dataclass
class Detection:
    bbox: tuple[float, float, float, float]  # x, y, w, h in pixels
    label: str
    confidence: float
    track_id: int | None = None
    extras: dict = field(default_factory=dict)


class ObjectDetector:
    """YOLO detector with one shared model instance for all cameras."""

    def __init__(self) -> None:
        self._model = None
        self.device = "cpu"
        self.available = False
        self.load_error = ""

    def load(self) -> bool:
        if self._model is not None:
            return True
        try:
            from ultralytics import YOLO  # optional dependency

            weights = settings.YOLO_WEIGHTS
            self._model = YOLO(weights)
            try:
                import torch

                if settings.ENABLE_GPU and torch.cuda.is_available():
                    self.device = "cuda"
            except Exception:
                self.device = "cpu"
            self.available = True
            logger.info("YOLO loaded (%s) on %s", weights, self.device)
            return True
        except Exception as exc:  # ultralytics/torch missing or download failed
            self.load_error = str(exc)[:300]
            logger.warning("YOLO unavailable: %s", self.load_error)
            return False

    def detect(self, frame_bgr: np.ndarray, conf_threshold: float | None = None) -> list[Detection]:
        if not self.load():
            return []
        conf = conf_threshold if conf_threshold is not None else settings.DETECTION_CONFIDENCE
        try:
            results = self._model.predict(
                frame_bgr,
                conf=conf,
                device=self.device,
                classes=list(VEHICLE_CLASSES.keys()) + ([PERSON_CLASS] if settings.DETECT_PERSONS else []),
                verbose=False,
            )
        except Exception as exc:
            logger.warning("inference failed: %s", exc)
            return []

        detections: list[Detection] = []
        for res in results:
            for box in res.boxes:
                cls_id = int(box.cls.item())
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                label = VEHICLE_CLASSES.get(cls_id) or (PERSON_LABEL if cls_id == PERSON_CLASS else str(cls_id))
                detections.append(
                    Detection(
                        bbox=(x1, y1, x2 - x1, y2 - y1),
                        label=label,
                        confidence=float(box.conf.item()),
                    )
                )
        return detections


class PlateReader:
    """ANPR: heuristic plate-region proposal + OCR text reading."""

    def __init__(self) -> None:
        self._ocr = None
        self._api3 = False
        self.available = False
        self.load_error = ""

    def load(self) -> bool:
        if self._ocr is not None:
            return True
        try:
            import paddleocr
            from paddleocr import PaddleOCR  # optional dependency

            # PaddleOCR 3.x removed use_angle_cls/show_log and now exposes a
            # doc-preprocessing pipeline we don't need for small plate crops;
            # disable it to load only det+rec. Support both APIs.
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            version = getattr(paddleocr, "__version__", "2.0") or "2.0"
            self._api3 = int(str(version).split(".")[0]) >= 3
            if self._api3:
                self._ocr = PaddleOCR(
                    lang="en",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    enable_mkldnn=False,  # paddle 3.x oneDNN backend breaks PP-OCR on Windows CPU
                )
            else:
                self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            self.available = True
            logger.info("PaddleOCR loaded (api %s)", "3.x" if self._api3 else "2.x")
            return True
        except Exception as exc:
            self.load_error = str(exc)[:300]
            logger.warning("PaddleOCR unavailable: %s", self.load_error)
            return False

    @staticmethod
    def propose_plate_crop(frame_bgr: np.ndarray, vehicle_bbox: tuple[float, float, float, float]) -> np.ndarray | None:
        """Heuristic plate region: lower-central part of the vehicle box.

        A dedicated plate-detector model can replace this without touching
        the rest of the pipeline.
        """
        H, W = frame_bgr.shape[:2]
        x, y, w, h = vehicle_bbox
        x2, y2 = min(x + w, W), min(y + h, H)
        x, y = max(x, 0), max(y, 0)
        vw, vh = x2 - x, y2 - y
        if vw < 24 or vh < 24:
            return None
        cx1 = int(x + vw * 0.15)
        cx2 = int(x + vw * 0.85)
        cy1 = int(y + vh * 0.55)
        cy2 = int(y + vh * 0.98)
        cx1, cy1 = max(cx1, 0), max(cy1, 0)
        if cx2 - cx1 < 12 or cy2 - cy1 < 8:
            return None
        return frame_bgr[cy1:cy2, cx1:cx2]

    @staticmethod
    def preprocess(crop_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 7, 40, 40)
        return cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)

    def _run_ocr(self, pre: np.ndarray) -> list[tuple[str, float]]:
        """Run OCR, returning (text, confidence) pairs. Handles 2.x and 3.x APIs."""
        if self._api3:
            # PaddleOCR 3.x: predict() -> results with rec_texts / rec_scores.
            # The 3.x predictor expects 3-channel input; our preprocess() is gray.
            if pre.ndim == 2:
                pre = cv2.cvtColor(pre, cv2.COLOR_GRAY2BGR)
            try:
                lines: list[tuple[str, float]] = []
                for res in self._ocr.predict(pre) or []:
                    getter = (res.get if isinstance(res, dict) else lambda k, d=None: getattr(res, k, d))
                    texts = getter("rec_texts", []) or []
                    scores = getter("rec_scores", []) or []
                    lines.extend((str(t), float(s)) for t, s in zip(texts, scores))
                return lines
            except Exception as exc:
                logger.warning("OCR failed: %s", exc)
                return []
        # PaddleOCR 2.x: ocr() -> [[ [box, (text, conf)], ... ]]
        try:
            result = self._ocr.ocr(pre, cls=True)
        except Exception as exc:
            logger.warning("OCR failed: %s", exc)
            return []
        lines = []
        for line in (result[0] if result else []) or []:
            try:
                lines.append((line[1][0], float(line[1][1])))
            except Exception:
                continue
        return lines

    def read_text(self, plate_crop_bgr: np.ndarray) -> tuple[str, float]:
        """Returns (normalized_text, confidence). ('', 0.0) when unreadable."""
        if not self.load() or plate_crop_bgr is None or plate_crop_bgr.size == 0:
            return "", 0.0
        pre = self.preprocess(plate_crop_bgr)
        lines = self._run_ocr(pre)
        if not lines:
            return "", 0.0
        best_text, best_conf = "", 0.0
        for text, conf in lines:
            cleaned = _PLATE_STRIP_RE.sub("", text.upper())
            if PLATE_RE.match(cleaned) and conf > best_conf:
                best_text, best_conf = cleaned, conf
        if not best_text:
            # keep the most confident raw fragment for the review workflow
            try:
                raw_text, raw_conf = max(lines, key=lambda l: l[1])
                best_text, best_conf = _PLATE_STRIP_RE.sub("", raw_text.upper()), raw_conf
            except Exception:
                return "", 0.0
        return best_text, best_conf

    @staticmethod
    def is_plausible(text: str) -> bool:
        return bool(text) and bool(PLATE_RE.match(text))


detector = ObjectDetector()
plate_reader = PlateReader()
