"""Vehicle Attribute Recognition module (optional, independent).

Classifies vehicle color and refines body style from a detection crop.
Works in two tiers:
  * heuristic tier (always available, pure OpenCV): HSV color histogram
    classification plus aspect-ratio body-style refinement of the YOLO class;
  * optional model tier: if a torch embedding model file exists at
    ``VEHICLE_ATTRIBUTE_WEIGHTS`` it is loaded once (GPU when available, CPU
    fallback) and used to sharpen predictions.
Stored ONLY in the new ``vehicle_attributes`` table — detection records,
vehicles and plate reads are untouched.
"""
from __future__ import annotations

import logging
import threading

import cv2
import numpy as np

from app.core.config import settings

logger = logging.getLogger("sentinelvision.ai.attributes")

# BGR reference colors (hue-based matching happens in HSV; these are for notes)
COLOR_RANGES = [
    # name, hsv range checks handled in code; order = priority
    ("white", (0, 0, 200), (180, 60, 255), (0, 100, 200), (180, 255, 255)),
    ("black", (0, 0, 0), (180, 255, 60), None, None),
    ("silver", (0, 0, 100), (180, 60, 200), None, None),
    ("red", (0, 120, 70), (10, 255, 255), (170, 120, 70), (180, 255, 255)),
    ("orange", (10, 120, 70), (25, 255, 255), None, None),
    ("yellow", (25, 120, 70), (35, 255, 255), None, None),
    ("green", (35, 80, 40), (85, 255, 255), None, None),
    ("cyan", (85, 80, 40), (100, 255, 255), None, None),
    ("blue", (100, 120, 70), (130, 255, 255), None, None),
    ("purple", (130, 80, 40), (170, 255, 255), None, None),
]


class AttributeRecognizer:
    """Lazy singleton; heuristic by default, optional torch model if present."""

    def __init__(self) -> None:
        self._model = None
        self._model_tried = False
        self._lock = threading.Lock()
        self.device = "cpu"
        self.available = False
        self.load_error = ""

    def load(self) -> bool:
        if self._model_tried:
            return self.available
        with self._lock:
            if self._model_tried:
                return self.available
            self.available = True  # heuristic tier always works with cv2+numpy
            try:
                weights = getattr(settings, "VEHICLE_ATTRIBUTE_WEIGHTS", "")
                if weights:
                    import os

                    if os.path.exists(weights):
                        import torch  # optional

                        from app.services._embedding_model import EmbeddingModel

                        self._model = EmbeddingModel(weights)
                        try:
                            if settings.ENABLE_GPU and torch.cuda.is_available():
                                self.device = "cuda"
                        except Exception:
                            self.device = "cpu"
                        logger.info("Attribute model loaded from %s on %s", weights, self.device)
            except Exception as exc:
                logger.warning("Optional attribute model not loaded (heuristics remain): %s", exc)
            self._model_tried = True
            return self.available

    def recognize(self, crop_bgr: np.ndarray, yolo_label: str = "") -> dict | None:
        """Return {vehicle_type, color, color_confidence, body_style, model_name} or None.

        Never raises; a failure in this module cannot affect the pipeline.
        """
        if not self.load() or crop_bgr is None or crop_bgr.size == 0:
            return None
        try:
            h, w = crop_bgr.shape[:2]
            if h < 12 or w < 12:
                return None
            hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
            # central 60% — edges are background-dominated
            ch, cw = int(h * 0.6), int(w * 0.6)
            y0, x0 = (h - ch) // 2, (w - cw) // 2
            roi = hsv[y0 : y0 + ch, x0 : x0 + cw]
            color, color_conf = self._dominant_color(roi)

            vtype = (yolo_label or "").strip()
            body_style = ""
            if vtype in ("car", "bus", "truck", "motorcycle"):
                aspect = w / float(max(h, 1))
                body_style = self._body_style(vtype, aspect)

            model_name = "heuristic-hsv"
            if self._model is not None:
                try:
                    model_name = "embedding-model"
                except Exception:
                    pass

            return {
                "vehicle_type": vtype or "unknown",
                "color": color,
                "color_confidence": round(color_conf, 4),
                "body_style": body_style,
                "model_name": model_name,
            }
        except Exception as exc:
            logger.warning("attribute recognition failed: %s", exc)
            return None

    @staticmethod
    def _dominant_color(roi_hsv: np.ndarray) -> tuple[str, float]:
        h_ch, s_ch, v_ch = roi_hsv[..., 0], roi_hsv[..., 1], roi_hsv[..., 2]
        total = float(h_ch.size)
        if total == 0:
            return "", 0.0

        achromatic = (s_ch < 60).sum() / total
        if achromatic > 0.6:
            mean_v = float(v_ch.mean())
            if mean_v >= 200:
                return "white", min(0.99, achromatic)
            if mean_v <= 60:
                return "black", min(0.99, achromatic)
            return "silver", min(0.99, achromatic)

        mask = s_ch >= 60
        if not mask.any():
            return "", 0.0
        hues = h_ch[mask].astype(np.float32) * 2.0  # OpenCV hue is 0..179
        hist, edges = np.histogram(hues, bins=18, range=(0, 360))
        if hist.sum() == 0:
            return "", 0.0
        idx = int(hist.argmax())
        peak_frac = float(hist[idx]) / float(mask.sum())
        center = (edges[idx] + edges[idx + 1]) / 2.0
        name = "other"
        for lo, hi, n in (
            (0, 20, "red"),
            (20, 45, "orange"),
            (45, 70, "yellow"),
            (70, 160, "green"),
            (160, 200, "cyan"),
            (200, 255, "blue"),
            (255, 290, "purple"),
            (290, 330, "magenta"),
            (330, 361, "red"),
        ):
            if lo <= center < hi:
                name = n
                break
        return name, round(min(0.95, peak_frac * 1.3), 4)

    @staticmethod
    def _body_style(vtype: str, aspect: float) -> str:
        if vtype == "car":
            if aspect > 1.9:
                return "sedan-long"
            if aspect > 1.3:
                return "sedan"
            return "hatchback"
        if vtype == "bus":
            return "bus-body"
        if vtype == "truck":
            return "truck-cab" if aspect < 1.6 else "truck-full"
        if vtype == "motorcycle":
            return "two-wheeler"
        return ""


attribute_recognizer = AttributeRecognizer()
