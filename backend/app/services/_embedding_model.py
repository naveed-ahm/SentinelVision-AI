"""Shared OPTIONAL torch embedding helper for the Re-ID and attribute modules.

Loaded lazily and only when a weights file exists. If torch/torchvision are
not installed, both consumers fall back to their pure-OpenCV heuristic tiers —
this file never raises into the pipeline. A tiny CNN (GlobalAveragePool over a
backbone) produces L2-normalized appearance embeddings; any checkpoint with a
compatible state dict can be dropped in for the hackathon demo.
"""
from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger("sentinelvision.ai.embedding")

INPUT_SIZE = (128, 128)  # (w, h)
_EMBED_DIM = 128


class EmbeddingModel:
    """Lazy single-instance wrapper around an optional torch embedding net."""

    def __init__(self, weights_path: str) -> None:
        self.weights_path = weights_path
        self._net = None
        self.device = "cpu"
        self.available = False
        self.load_error = ""

    def load(self) -> bool:
        if self._net is not None:
            return True
        try:
            import torch  # optional dependency

            from torch import nn

            class _TinyCNN(nn.Module):
                def __init__(self) -> None:
                    super().__init__()
                    def block(cin, cout):
                        return nn.Sequential(
                            nn.Conv2d(cin, cout, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2)
                        )

                    self.features = nn.Sequential(
                        block(3, 16), block(16, 32), block(32, 64), block(64, _EMBED_DIM)
                    )
                    self.pool = nn.AdaptiveAvgPool2d(1)

                def forward(self, x):
                    x = self.features(x)
                    x = self.pool(x).flatten(1)
                    return nn.functional.normalize(x, p=2, dim=1)

            net = _TinyCNN()
            state = torch.load(self.weights_path, map_location="cpu")
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            net.load_state_dict(state, strict=False)
            try:
                if __import__("app.core.config", fromlist=["settings"]).settings.ENABLE_GPU and torch.cuda.is_available():
                    self.device = "cuda"
            except Exception:
                self.device = "cpu"
            net.to(self.device).eval()
            self._net = net
            self.available = True
            logger.info("Embedding model loaded from %s on %s", self.weights_path, self.device)
            return True
        except Exception as exc:
            self.load_error = str(exc)[:300]
            logger.warning("Embedding model unavailable: %s", self.load_error)
            return False

    def embed(self, crop_bgr: np.ndarray) -> list[float] | None:
        """L2-normalized appearance embedding for a crop, or None."""
        if not self.load() or crop_bgr is None or crop_bgr.size == 0:
            return None
        try:
            import torch

            img = cv2.resize(crop_bgr, INPUT_SIZE)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(self.device)
            with torch.no_grad():
                vec = self._net(tensor)
            return vec.squeeze(0).cpu().tolist()
        except Exception as exc:
            logger.warning("embedding failed: %s", exc)
            return None


def heuristic_embedding(crop_bgr: np.ndarray) -> list[float] | None:
    """Dependency-free appearance descriptor (HSV hist + edges), L2-normalized.

    Used by the Re-ID module when no torch model is available so the feature
    still functions end-to-end (with clearly lower discriminative power).
    """
    try:
        if crop_bgr is None or crop_bgr.size == 0:
            return None
        h, w = crop_bgr.shape[:2]
        if h < 12 or w < 12:
            return None
        img = cv2.resize(crop_bgr, INPUT_SIZE)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [12, 8], [0, 180, 0, 256]).flatten()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        sobel = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        edge = np.histogram(np.abs(sobel).flatten(), bins=8, range=(0, 256))[0]
        vec = np.concatenate([hist * 0.01, edge * 0.001]).astype(np.float32)
        norm = float(np.linalg.norm(vec))
        if norm <= 0:
            return None
        return (vec / norm).tolist()
    except Exception:
        return None
