"""Anomaly Detection module (optional, independent).

Flags unusual vehicle MOVEMENT for human review using transparent heuristics
over the existing tracker's bbox history: high estimated speed, loitering
(long dwell), and wrong-way travel (against the per-camera dominant direction).

HARD POLICY: outputs are review events ONLY. Nothing here labels behavior as
criminal — severity is always "info", wording says "review", and the module
never creates vehicle identities, blocks streams, or interrupts the pipeline.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger("sentinelvision.ai.anomaly")


@dataclass
class _CamAnomalyState:
    dominant_direction: float = 0.0  # smoothed mean dx per sample (px)
    direction_samples: int = 0
    last_review_ts: float = 0.0
    camera_scale: float = 0.0  # px per meter estimate (median bbox width)
    width_samples: list = field(default_factory=list)


class AnomalyEngine:
    """Singleton per-camera movement statistics (lazy, thread-safe)."""

    def __init__(self) -> None:
        self._states: dict[int, _CamAnomalyState] = {}
        self._lock = threading.Lock()
        self.available = False
        self.load_error = ""

    def load(self) -> bool:
        if not self.available:
            self.available = True  # heuristic tier: no external deps
        return self.available

    def _state_for(self, camera_id: int) -> _CamAnomalyState:
        st = self._states.get(camera_id)
        if st is None:
            st = _CamAnomalyState()
            self._states[camera_id] = st
        return st

    @staticmethod
    def _estimate_scale(widths) -> float:
        """Median vehicle width in px -> meters (≈1.8 m median car width)."""
        if not widths:
            return 0.0
        ws = sorted(widths)[-50:]
        median_px = ws[len(ws) // 2]
        return median_px / 1.8 if median_px > 0 else 0.0

    def evaluate_track(
        self,
        *,
        camera_id: int,
        track_id: int,
        label: str,
        history: list[tuple[float, float, float, float]],
        sample_interval: float,
    ) -> dict | None:
        """Evaluate one track's movement. Returns a review dict or None.

        Never raises; all failures return None so the pipeline is untouched.
        """
        if not settings.ENABLE_ANOMALY or not self.load():
            return None
        try:
            if label == "person" or len(history) < settings.ANOMALY_MIN_TRACK_HISTORY:
                return None
            st = self._state_for(camera_id)

            # learn dominant direction + scale from recent motion
            centers = [(x + w / 2.0, y + h / 2.0) for x, y, w, h in history]
            dxs = [centers[i + 1][0] - centers[i][0] for i in range(len(centers) - 1)]
            recent_dx = dxs[-8:]
            mean_dx = sum(recent_dx) / len(recent_dx) if recent_dx else 0.0
            with self._lock:
                if st.direction_samples < 400:
                    alpha = 0.05
                    st.dominant_direction = (alpha * mean_dx) + (1 - alpha) * st.dominant_direction
                    st.direction_samples += 1
                widths = [w for _, _, w, _ in history]
                st.width_samples = (st.width_samples + widths)[-200:]
                st.camera_scale = self._estimate_scale(st.width_samples)

            now_monotonic = time.monotonic()
            findings: list[dict] = []

            # 1) High estimated speed (px/sample -> m/s via camera scale)
            if st.camera_scale > 0 and sample_interval > 0:
                speed_px_s = abs(mean_dx) / sample_interval
                speed_ms = speed_px_s / st.camera_scale
                speed_kmph = speed_ms * 3.6
                if speed_kmph > settings.ANOMALY_SPEED_LIMIT_KMPH:
                    findings.append(
                        {
                            "anomaly_type": "speed",
                            "score": round(min(1.0, speed_kmph / 200.0), 3),
                            "detail": f"Estimated {speed_kmph:.0f} km/h exceeds review threshold "
                            f"({settings.ANOMALY_SPEED_LIMIT_KMPH:.0f} km/h).",
                        }
                    )

            # 2) Loitering: near-zero displacement over the history window
            centers_now = centers[-1]
            centers_start = centers[0]
            net = (
                (centers_now[0] - centers_start[0]) ** 2 + (centers_now[1] - centers_start[1]) ** 2
            ) ** 0.5
            window_s = len(history) * sample_interval
            if window_s >= 20 and net < 0.10 * max(st.camera_scale, 1.0) * len(history):
                findings.append(
                    {
                        "anomaly_type": "loitering",
                        "score": round(min(1.0, window_s / 120.0), 3),
                        "detail": f"Vehicle stationary/dwelling ~{window_s:.0f}s within view — review recommended.",
                    }
                )

            # 3) Wrong-way travel vs learned dominant direction
            if st.direction_samples >= 40 and abs(st.dominant_direction) > 1.0:
                if mean_dx * st.dominant_direction < 0 and abs(mean_dx) > 2.0:
                    findings.append(
                        {
                            "anomaly_type": "direction",
                            "score": 0.6,
                            "detail": "Travel direction opposes the camera's dominant flow — review recommended.",
                        }
                    )

            if not findings:
                return None

            strongest = max(findings, key=lambda f: f["score"])
            with self._lock:
                if now_monotonic - st.last_review_ts < settings.ANOMALY_COOLDOWN_SECONDS:
                    return None  # one review per camera per cooldown window
                st.last_review_ts = now_monotonic
            return {
                "anomaly_type": strongest["anomaly_type"],
                "score": strongest["score"],
                "detail": strongest["detail"],
                "all_findings": findings,
            }
        except Exception as exc:
            logger.warning("anomaly evaluation failed: %s", exc)
            return None

    def status(self) -> dict:
        with self._lock:
            return {
                "cameras_tracked": len(self._states),
                "direction_calibrated": sum(1 for s in self._states.values() if s.direction_samples >= 40),
            }

    def reset(self) -> None:
        with self._lock:
            self._states.clear()


anomaly_engine = AnomalyEngine()
