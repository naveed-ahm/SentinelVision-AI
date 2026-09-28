"""Multi-object tracking (ByteTrack-style IoU tracker) and cross-camera correlation.

The tracker is a dependency-free IoU+centroid tracker following the ByteTrack
philosophy: keep low-confidence detections alive briefly instead of dropping
them. A production deployment can swap in the official ByteTrack
implementation via the same interface.
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Track:
    track_id: int
    label: str
    bbox: tuple[float, float, float, float]
    confidence: float
    first_seen: float
    last_seen: float
    hits: int = 1
    age: int = 0
    misses: int = 0
    confirmed_plate: str | None = None  # set when a high-confidence ANPR read binds to this track
    history: list[tuple[float, float, float, float]] = field(default_factory=list)


class IoUTracker:
    def __dataclass_fields__(self):  # pragma: no cover
        return Track.__dataclass_fields__

    def __init__(self, iou_threshold: float = 0.3, max_misses: int = 12, min_hits: int = 2) -> None:
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses
        self.min_hits = min_hits
        self._tracks: dict[int, Track] = {}
        self._next_id = 1

    @staticmethod
    def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
        ax1, ay1, aw, ah = a
        bx1, by1, bw, bh = b
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx2, by2 = bx1 + bw, by1 + bh
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        inter = iw * ih
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0.0

    def update(self, detections: list, timestamp: float) -> list[Track]:
        unmatched_dets = list(range(len(detections)))
        matches: list[tuple[int, int]] = []

        # Greedy IoU matching, highest confidence first.
        for t in sorted(self._tracks.values(), key=lambda tr: tr.confidence, reverse=True):
            if t.misses >= self.max_misses:
                continue
            best_iou, best_det = self.iou_threshold, None
            for di in unmatched_dets:
                d = detections[di]
                if d.label != t.label:
                    continue
                iou = self._iou(t.bbox, d.bbox)
                if iou > best_iou:
                    best_iou, best_det = iou, di
            if best_det is not None:
                d = detections[best_det]
                t.bbox = d.bbox
                t.confidence = d.confidence
                t.hits += 1
                t.misses = 0
                t.last_seen = timestamp
                t.history = ([*t.history[-39:], d.bbox])
                matches.append((t.track_id, best_det))
                unmatched_dets.remove(best_det)
                if t.confirmed_plate is None and getattr(d, "extras", {}).get("plate_text"):
                    plate = d.extras.get("plate_text")
                    if d.extras.get("plate_confidence", 0) >= 0.8:
                        t.confirmed_plate = plate

        # Age and prune dead tracks.
        for tid in list(self._tracks):
            t = self._tracks[tid]
            if t.track_id not in [m[0] for m in matches]:
                t.misses += 1
                t.age += 1
            if t.misses >= self.max_misses:
                del self._tracks[tid]

        # New tracks for unmatched detections.
        for di in unmatched_dets:
            d = detections[di]
            t = Track(
                track_id=self._next_id,
                label=d.label,
                bbox=d.bbox,
                confidence=d.confidence,
                first_seen=timestamp,
                last_seen=timestamp,
            )
            self._tracks[self._next_id] = t
            self._next_id += 1

        return [t for t in self._tracks.values() if t.hits >= self.min_hits or t.misses == 0]

    @property
    def active_tracks(self) -> list[Track]:
        return list(self._tracks.values())

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1


def correlate_sightings(
    sightings: list[dict],
    min_confidence: float = 0.8,
    max_gap_minutes: int = 30,
) -> dict[str, list[dict]]:
    """Group sightings across cameras by *confirmed* registration number only.

    Visual similarity is deliberately NOT used as evidence for cross-camera
    identity: metadata + plate text are the only reliable signals in this PoC.
    """
    groups: dict[str, list[dict]] = {}
    for s in sightings:
        plate = s.get("registration_number")
        if not plate or s.get("ocr_confidence", 0) < min_confidence:
            continue
        groups.setdefault(plate, []).append(s)

    result: dict[str, list[dict]] = {}
    for plate, items in groups.items():
        items.sort(key=lambda s: s["timestamp"])
        # split into chains when the gap between consecutive sightings is too large
        chain: list[dict] = []
        chains: list[list[dict]] = []
        prev_ts = None
        for s in items:
            if prev_ts is not None:
                gap_min = (s["timestamp"] - prev_ts).total_seconds() / 60.0
                if gap_min > max_gap_minutes:
                    chains.append(chain)
                    chain = []
            chain.append(s)
            prev_ts = s["timestamp"]
        if chain:
            chains.append(chain)
        for i, c in enumerate(chains):
            key = plate if i == 0 else f"{plate}#{i + 1}"
            result[key] = c
    return result
