"""Camera management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_admin, require_operator
from app.models.camera import Camera, CameraCredential
from app.models.user import User, utcnow
from app.schemas.schemas import CameraCreate, CameraOut, CameraTestResult, CameraUpdate
from app.services.audit import audit
from app.services.camera_service import redact_url, test_camera_connection
from app.services.storage import cleanup_camera_media

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _to_out(cam: Camera) -> CameraOut:
    data = CameraOut.model_validate(cam)
    data.rtsp_url = redact_url(cam.rtsp_url or "")
    return data


@router.get("", response_model=list[CameraOut])
def list_cameras(
    status: str | None = Query(None, pattern="^(online|offline|error|disabled)$"),
    protocol: str | None = Query(None, pattern="^(rtsp|file|webcam)$"),
    location: str | None = None,
    search: str | None = None,
    sort: str = Query("name", pattern="^(name|code|status|created_at)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = db.query(Camera)
    if status:
        q = q.filter(Camera.status == status)
    if protocol:
        q = q.filter(Camera.protocol == protocol)
    if location:
        q = q.filter(Camera.location_name.ilike(f"%{location}%"))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Camera.name.ilike(like), Camera.code.ilike(like), Camera.location_name.ilike(like)))
    col = getattr(Camera, sort)
    q = q.order_by(col.desc() if order == "desc" else col.asc())
    return [_to_out(c) for c in q.all()]


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
    request: Request = None,
):
    if db.query(Camera).filter(Camera.code == payload.code).first():
        raise HTTPException(409, "Camera code already exists")
    cam = Camera(
        name=payload.name,
        code=payload.code,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        manufacturer=payload.manufacturer,
        model=payload.model,
        protocol=payload.protocol,
        rtsp_url=payload.rtsp_url,
        description=payload.description,
        enabled=payload.enabled,
        detection_enabled=payload.detection_enabled,
        is_demo=settings.DEMO_MODE,
    )
    if payload.credential:
        cam.credential = CameraCredential(**payload.credential.model_dump())
    db.add(cam)
    db.commit()
    db.refresh(cam)
    audit(db, request, user, "camera.create", cam.code)
    return _to_out(cam)


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    return _to_out(cam)


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
    request: Request = None,
):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    data = payload.model_dump(exclude_unset=True)
    cred_data = data.pop("credential", None)
    for k, v in data.items():
        setattr(cam, k, v)
    if cred_data is not None:
        if cam.credential is None:
            cam.credential = CameraCredential()
        for k, v in cred_data.items():
            setattr(cam.credential, k, v)
    cam.updated_at = utcnow()
    db.commit()
    db.refresh(cam)
    audit(db, request, user, "camera.update", cam.code, ",".join(data.keys()))
    return _to_out(cam)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    request: Request = None,
):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    code = cam.code
    audit(db, request, user, "camera.delete", code)
    db.delete(cam)
    db.commit()
    cleanup_camera_media(code)


@router.post("/{camera_id}/test", response_model=CameraTestResult)
def test_connection(
    camera_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
    request: Request = None,
):
    """Time-boxed connection test. Runs in a threadpool so the API is not blocked."""
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    ok, message, latency = test_camera_connection(cam)
    audit(db, request, user, "camera.test", cam.code, f"ok={ok}")
    return CameraTestResult(camera_id=camera_id, ok=ok, message=message, latency_ms=latency)


@router.post("/{camera_id}/enable", response_model=CameraOut)
def enable_camera(camera_id: int, db: Session = Depends(get_db), user: User = Depends(require_operator), request: Request = None):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    cam.enabled = True
    cam.status = "offline"
    db.commit()
    db.refresh(cam)
    audit(db, request, user, "camera.enable", cam.code)
    return _to_out(cam)


@router.post("/{camera_id}/disable", response_model=CameraOut)
def disable_camera(camera_id: int, db: Session = Depends(get_db), user: User = Depends(require_operator), request: Request = None):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    cam.enabled = False
    cam.status = "disabled"
    db.commit()
    db.refresh(cam)
    audit(db, request, user, "camera.disable", cam.code)
    return _to_out(cam)
