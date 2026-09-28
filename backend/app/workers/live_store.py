"""Disk-backed live frame store.

The ingestion worker (separate process) publishes the latest annotated JPEG
for each camera here; any API process can then serve MJPEG/WS streams from
it. Atomic writes keep readers consistent. For multi-node deployments this is
the seam to replace with Redis/object storage.
"""
import json
import time
from pathlib import Path

from app.core.config import settings


class LiveStore:
    STALE_AFTER = 30.0  # seconds

    def __init__(self, media_dir: str | None = None) -> None:
        self.base = Path(media_dir or settings.MEDIA_DIR) / "live"
        self.base.mkdir(parents=True, exist_ok=True)

    def _jpg(self, code: str) -> Path:
        return self.base / f"{code}.jpg"

    def _meta(self, code: str) -> Path:
        return self.base / f"{code}.json"

    def publish(self, code: str, seq: int, annotated_jpeg: bytes) -> None:
        """Atomic publish: write temp files, then rename."""
        try:
            jpg_tmp = Path(str(self._jpg(code)) + ".tmp")
            jpg_tmp.write_bytes(annotated_jpeg)
            meta_tmp = Path(str(self._meta(code)) + ".tmp")
            meta_tmp.write_text(json.dumps({"seq": seq, "ts": time.time()}))
            jpg_tmp.replace(self._jpg(code))
            meta_tmp.replace(self._meta(code))
        except OSError:
            pass  # never crash ingestion on storage hiccups

    def latest(self, code: str, after_seq: int = -1) -> tuple[bytes, int] | None:
        try:
            meta = json.loads(self._meta(code).read_text())
            seq = int(meta.get("seq", -1))
            if seq <= after_seq:
                return None
            if time.time() - float(meta.get("ts", 0)) > self.STALE_AFTER:
                return None
            return self._jpg(code).read_bytes(), seq
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def is_fresh(self, code: str) -> bool:
        try:
            meta = json.loads(self._meta(code).read_text())
            return time.time() - float(meta.get("ts", 0)) < self.STALE_AFTER
        except (OSError, ValueError, json.JSONDecodeError):
            return False

    def fresh_codes(self) -> list[str]:
        return [p.stem for p in self.base.glob("*.json") if self.is_fresh(p.stem)]


live_store = LiveStore()
