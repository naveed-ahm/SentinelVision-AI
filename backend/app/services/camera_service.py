"""Camera service: RTSP URL assembly, redaction and connection testing.

Secrets (username/password) live in the separate camera_credentials table and
are combined into the effective RTSP URL only inside the ingestion worker.
API responses always return a redacted URL.
"""
import re
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.models.camera import Camera, CameraCredential

_REDACT_RE = re.compile(r"//([^/@]+)@")
_USERINFO_RE = re.compile(r"//([^/@]+)@")


def redact_url(url: str) -> str:
    """Replace userinfo in a URL with a placeholder."""
    if not url:
        return ""
    return _REDACT_RE.sub("//***:***@", url)


def build_effective_url(camera: Camera) -> str:
    """Combine camera.rtsp_url with credentials (if any) into a connectable URL."""
    url = camera.rtsp_url or ""
    if not url:
        return ""
    if camera.credential and camera.credential.username:
        try:
            parts = urlsplit(url)
            host = parts.netloc.rsplit("@", 1)[-1]
            secret = camera.credential.secret or ""
            from urllib.parse import quote

            userinfo = f"{quote(camera.credential.username)}:{quote(secret)}@"
            url = urlunsplit((parts.scheme, userinfo + host, parts.path, parts.query, parts.fragment))
        except Exception:
            pass
    return url


def effective_url_for_camera(db: Session, camera_id: int) -> str:
    cam = db.get(Camera, camera_id)
    if cam is None:
        return ""
    if cam.credential is None:
        _ = cam.credential
    return build_effective_url(cam)


def test_camera_connection(camera: Camera, timeout_seconds: float = 6.0) -> tuple[bool, str, float | None]:
    """Try to open the stream in a subprocess-safe, time-boxed way.

    Returns (ok, message, latency_ms). Never raises.
    """
    import time

    from app.core.config import settings

    url = build_effective_url(camera)
    protocol = camera.protocol or "rtsp"
    if not url and protocol == "rtsp":
        return False, "No RTSP URL configured", None
    if protocol == "file":
        import os

        if not url or not os.path.exists(url):
            return False, f"Video file not found: {redact_url(url)}", None

    start = time.monotonic()
    try:
        import cv2

        if protocol == "rtsp":
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        else:
            cap = cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout_seconds * 1000))
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(timeout_seconds * 1000))
        ok_frame = False
        if cap.isOpened():
            ok_frame, _frame = cap.read()
        cap.release()
        latency = (time.monotonic() - start) * 1000.0
        if ok_frame:
            return True, "Connection OK", latency
        return False, "Could not open stream or read a frame", latency
    except Exception as exc:
        return False, f"Connection failed: {exc}", (time.monotonic() - start) * 1000.0
