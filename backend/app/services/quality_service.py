"""Image Quality Assessment module (optional, independent).

Scores sampled frames for blur, brightness and visibility on a 0..1 scale and
produces a composite usability score. Pure OpenCV/numpy — no heavy optional
dependencies — so this module works everywhere; it can still be disabled via
``ENABLE_QUALITY=false``. It NEVER blocks or alters the existing pipeline:
quality rows are stored separately and only surfaced as informational status.
"""
from __future__ import annotations

import logging
import threading

import cv2
import numpy as np

from app.core.config import settings

logger = logging.getLogger("sentinelvision.ai.quality")


class QualityAssessor:
    """Stateless frame scorer with lazy availability check (singleton)."""

    def __init__(self) -> None:
        self._initialized = False
        self._init_lock = threading.Lock()
        self.available = False
        self.load_error = ""

    def load(self) -> bool:
        """One-time initialization; safe to call repeatedly (no repeated loads)."""
        if self._initialized:
            return self.available
        with self._init_lock:
            if self._initialized:
                return self.available
            try:
                import cv2  # noqa: F401 — hard dependency; checked for honesty

                self.available = True
            except Exception as exc:
                self.load_error = str(exc)[:300]
                logger.warning("Quality module unavailable: %s", self.load_error)
            self._initialized = True
            return self.available

    @staticmethod
    def _blur_score(gray: np.ndarray) -> float:
        """Variance-of-Laplacian sharpness mapped to 0..1 (saturates ~600)."""
        var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return min(var / 600.0, 1.0)

    @staticmethod
    def _brightness_score(gray: np.ndarray) -> float:
        """Mean luma mapped to 0..1 with 110-160 treated as ideal."""
        mean = float(gray.mean())
        return max(0.0, 1.0 - abs(mean - 135.0) / 135.0)

    @staticmethod
    def _visibility_score(gray: np.ndarray) -> float:
        """RMS contrast mapped to 0..1 (saturates ~64) — low contrast = haze/night."""
        rms = float(gray.std())
        return min(rms / 64.0, 1.0)

    def assess(self, frame_bgr: np.ndarray) -> dict | None:
        """Score one frame. Returns None (never raises) when unusable input."""
        if not self.load() or frame_bgr is None or frame_bgr.size == 0:
            return None
        try:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            if gray.size == 0:
                return None
            blur = self._blur_score(gray)
            bright = self._brightness_score(gray)
            vis = self._visibility_score(gray)
            composite = round(0.5 * blur + 0.3 * bright + 0.2 * vis, 4)
            if composite >= 0.6:
                verdict = "good"
            elif composite >= settings.QUALITY_LOW_THRESHOLD:
                verdict = "degraded"
            else:
                verdict = "poor"
            return {
                "composite": composite,
                "blur_score": round(blur, 4),
                "brightness_score": round(bright, 4),
                "visibility_score": round(vis, 4),
                "verdict": verdict,
            }
        except Exception as exc:  # any cv2 failure must not touch the pipeline
            logger.warning("quality assess failed: %s", exc)
            return None


quality_assessor = QualityAssessor()
