"""Media storage abstraction.

Development: local filesystem under settings.MEDIA_DIR.
Production: swap LocalStorage for an S3/MinIO implementation with the same
interface; only this module knows where bytes live.
"""
import shutil
import uuid
from pathlib import Path

from app.core.config import settings


class LocalStorage:
    def __init__(self, base_dir: str) -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def _full(self, rel: str) -> Path:
        p = (self.base / rel).resolve()
        if self.base.resolve() not in p.parents and p.parent != self.base.resolve():
            raise ValueError("path escapes media root")
        return p

    def save_jpeg(self, data: bytes, subdir: str, prefix: str) -> str:
        day = uuid.uuid4().hex[:8]
        rel = f"{subdir}/{prefix}_{day}.jpg"
        p = self._full(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return rel

    def open_bytes(self, rel: str) -> bytes:
        return self._full(rel).read_bytes()

    def exists(self, rel: str) -> bool:
        try:
            return self._full(rel).exists()
        except ValueError:
            return False

    def delete_prefix(self, prefix: str) -> int:
        n = 0
        root = self.base / prefix
        if root.exists():
            for f in root.rglob("*"):
                if f.is_file():
                    f.unlink()
                    n += 1
        return n


class NullStorage:
    """Fallback when storage backend is unavailable."""

    def save_jpeg(self, data: bytes, subdir: str, prefix: str) -> str:  # pragma: no cover
        return ""

    def open_bytes(self, rel: str) -> bytes:  # pragma: no cover
        raise FileNotFoundError(rel)

    def exists(self, rel: str) -> bool:  # pragma: no cover
        return False

    def delete_prefix(self, prefix: str) -> int:  # pragma: no cover
        return 0


storage = LocalStorage(settings.MEDIA_DIR)


def cleanup_camera_media(camera_code: str) -> None:
    """Remove media files for a deleted camera (best-effort)."""
    shutil.rmtree(Path(settings.MEDIA_DIR) / camera_code, ignore_errors=True)
