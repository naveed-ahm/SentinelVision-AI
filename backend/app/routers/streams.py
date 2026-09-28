"""Stream endpoints: MJPEG gateway for browser playback + worker status."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_flexible
from app.models.camera import Camera
from app.models.user import User
from app.schemas.schemas import WorkerStatus

router = APIRouter(prefix="/streams", tags=["streams"])


def _mjpeg_stream(camera_code: str):
    """Yield multipart MJPEG from the cross-process live store."""
    from app.workers.live_store import live_store
    import time as _time

    last_seq = -1
    boundary = b"--frame\r\n"
    while True:
        latest = live_store.latest(camera_code, last_seq)
        if latest is None:
            yield boundary
            _time.sleep(0.5)
            continue
        data, last_seq = latest
        yield (
            boundary
            + b"Content-Type: image/jpeg\r\nContent-Length: "
            + str(len(data)).encode()
            + b"\r\n\r\n"
            + data
            + b"\r\n"
        )


@router.get("/{camera_id}/mjpeg")
def mjpeg(camera_id: int, _user: User = Depends(get_current_user_flexible), db: Session = Depends(get_db)):
    """Browser-playable Motion-JPEG stream fed by the ingestion worker.
    Accepts ?access_token= because <img> tags cannot set headers."""
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    if not cam.enabled:
        raise HTTPException(409, "Camera is disabled")
    return StreamingResponse(
        _mjpeg_stream(cam.code),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{camera_id}/snapshot")
def snapshot(camera_id: int, _user: User = Depends(get_current_user_flexible), db: Session = Depends(get_db)):
    """Latest annotated frame as a plain JPEG (for dashboard previews)."""
    from fastapi import Response

    from app.workers.live_store import live_store

    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    latest = live_store.latest(cam.code, -1)
    if latest is None:
        raise HTTPException(404, "No live frame available (camera offline or no source)")
    return Response(content=latest[0], media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/worker/status", response_model=WorkerStatus)
def worker_status(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Worker status is derived from shared state (DB camera rows + live store),
    so it is accurate even when the worker runs in a separate process."""
    from app.workers.live_store import live_store
    from app.services.detection_service import detector, plate_reader

    cams = db.query(Camera).filter(Camera.enabled.is_(True)).all()
    states = {str(c.id): ("online" if live_store.is_fresh(c.code) else c.status) for c in cams}
    running = any(s == "online" for s in states.values())
    return WorkerStatus(
        running=running,
        cameras=states,
        detector_ready=detector.available,
        detector_device=detector.device,
        ocr_ready=plate_reader.available,
        demo_mode=settings.DEMO_MODE,
    )
