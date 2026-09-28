"""Frame spooler: per-camera ring buffers of annotated JPEG frames.

The ingestion worker (separate process) pushes frames here; the API process
consumes them for MJPEG/WS streaming. In the single-process PoC layout they
share the module. A Redis-backed spooler can replace this for multi-node use.
"""
import asyncio
import threading
from collections import deque
from dataclasses import dataclass


@dataclass
class FrameEntry:
    seq: int
    jpeg: bytes
    annotated_jpeg: bytes
    ts: float


class FrameSpooler:
    def __init__(self, maxlen: int = 6) -> None:
        self._maxlen = maxlen
        self._buffers: dict[int, deque[FrameEntry]] = {}
        self._latest_seq: dict[int, int] = {}
        self._lock = threading.Lock()
        self.camera_states: dict[int, object] = {}
        self.running = False

    def push(self, camera_id: int, entry: FrameEntry) -> None:
        with self._lock:
            buf = self._buffers.setdefault(camera_id, deque(maxlen=self._maxlen))
            buf.append(entry)
            self._latest_seq[camera_id] = entry.seq

    def push_annotated(self, camera_id: int, entry: FrameEntry) -> None:
        self.push(camera_id, entry)

    def get_latest(self, camera_id: int, after_seq: int = -1) -> tuple[bytes, int] | None:
        with self._lock:
            buf = self._buffers.get(camera_id)
            if not buf:
                return None
            entry = buf[-1]
            if entry.seq <= after_seq:
                return None
            return entry.jpeg, entry.seq

    def get_latest_annotated(self, camera_id: int, after_seq: int = -1) -> tuple[bytes, int] | None:
        with self._lock:
            buf = self._buffers.get(camera_id)
            if not buf:
                return None
            entry = buf[-1]
            if entry.seq <= after_seq:
                return None
            return entry.annotated_jpeg, entry.seq

    def active_cameras(self) -> list[int]:
        with self._lock:
            return list(self._buffers.keys())

    def active_count(self) -> int:
        with self._lock:
            return len(self._buffers)

    def clear_camera(self, camera_id: int) -> None:
        with self._lock:
            self._buffers.pop(camera_id, None)
            self._latest_seq.pop(camera_id, None)


spooler = FrameSpooler()


class SourceState:
    CONNECTING = "connecting"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"

    def __init__(self, name: str) -> None:
        self.value = name
