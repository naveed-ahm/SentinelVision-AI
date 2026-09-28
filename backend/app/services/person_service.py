"""Person Detection module (optional, independent of the vehicle pipeline).

Runs its OWN model instance with its own weights so person detection can be
enabled/disabled without touching the existing vehicle detection service.
Records presence-only detections (no face recognition, no identity inference)
in the new ``person_detections`` table, annotated separately from vehicles.
"""
from __future__ import annotations

import logging
import threading

from app.core.config import settings

logger = logging.getLogger("sentinelvision.ai.person")

PERSON_LABEL = "person"
PERSON_CLASS_ID = 0


class PersonDetector:
    """Lazy singleton with its own model instance; degrades like other modules."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()
        self.device = "cpu"
        self.available = False
        self.load_error = ""

    def load(self) -> bool:
        if self.available or self.load_error:
            return self.available
        with self._lock:
            if self.available or self.load_error:
                return self.available
            try:
                from ultralytics import YOLO  # optional dependency, same as the vehicle detector

                weights = settings.PERSON_MODEL_WEIGHTS
                self._model = YOLO(weights)  # independent instance, not shared with vehicle pipeline
                try:
                    import torch

                    if settings.ENABLE_GPU and torch.cuda.is_available():
                        self.device = "cuda"
                except Exception:
                    self.device = "cpu"
                self.available = True
                logger.info("Person model loaded (%s) on %s", weights, self.device)
            except Exception as exc:  # ultralytics/torch missing or download failed
                self.load_error = str(exc)[:300]
                logger.warning("Person model unavailable: %s", self.load_error)
            return self.available

    def detect(self, frame_bgr) -> list[dict]:
        """Return [{bbox=(x,y,w,h), confidence}] for person class only.

        Empty list when unavailable or on any failure — never raises into the
        worker thread.
        """
        if not settings.ENABLE_PERSON_MODEL:
            return []
        if not self.load() or frame_bgr is None:
            return []
        try:
            results = self._model.predict(
                frame_bgr,
                conf=0.35,
                classes=[PERSON_CLASS_ID],
                device=self.device,
                verbose=False,
            )
            out: list[dict] = []
            for res in results:
                for box in res.boxes:
                    x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                    out.append(
                        {
                            "bbox": (x1, y1, x2 - x1, y2 - y1),
                            "confidence": float(box.conf.item()),
                        }
                    )
            return out
        except Exception as exc:
            logger.warning("person detection failed: %s", exc)
            return []

    def status(self) -> dict:
        return {
            "available": self.available,
            "device": self.device,
            "error": self.load_error,
        }


person_detector = PersonDetector()
