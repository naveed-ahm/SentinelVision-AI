"""Vehicle search and cross-camera tracking endpoints."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.camera import Camera
from app.models.event import DetectionEvent, PlateRead, Vehicle, VehicleSighting
from app.models.user import User
from app.schemas.schemas import VehicleDetail, VehicleOut, VehiclePage, VehicleSightingOut

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def _sighting_out(s: VehicleSighting) -> VehicleSightingOut:
    e = s.event
    pr = e.plate_read if e else None
    cam = s.camera
    return VehicleSightingOut(
        id=s.id,
        vehicle_id=s.vehicle_id,
        event_id=s.event_id,
        camera_id=s.camera_id,
        timestamp=s.timestamp,
        camera_name=cam.name if cam else None,
        registration_number=(pr.corrected_text or pr.plate_text) if pr else None,
        object_class=e.object_class if e else None,
        confidence=e.confidence if e else None,
        image_path=e.image_path if e else "",
        frame_path=e.frame_path if e else "",
        ocr_confidence=pr.ocr_confidence if pr else None,
    )


@router.get("", response_model=VehiclePage)
def search_vehicles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    registration_number: str | None = None,
    vehicle_class: str | None = None,
    camera_id: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Server-side filtered, paginated vehicle search."""
    q = db.query(Vehicle)
    if registration_number:
        like = f"%{registration_number.upper()}%"
        q = q.filter(Vehicle.registration_number.like(like))
    if vehicle_class:
        q = q.filter(Vehicle.vehicle_class == vehicle_class)
    if camera_id or start or end:
        q = q.join(VehicleSighting)
        if camera_id:
            q = q.filter(VehicleSighting.camera_id == camera_id)
        if start:
            q = q.filter(VehicleSighting.timestamp >= start)
        if end:
            q = q.filter(VehicleSighting.timestamp <= end)
    total = q.distinct().count()
    items = (
        q.distinct()
        .order_by(Vehicle.last_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return VehiclePage(
        items=[VehicleOut.model_validate(v) for v in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tracked", response_model=list[VehicleOut])
def recently_tracked(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(Vehicle).order_by(Vehicle.last_seen_at.desc()).limit(limit).all()


@router.get("/{vehicle_id}", response_model=VehicleDetail)
def vehicle_detail(vehicle_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")
    sightings = (
        db.query(VehicleSighting)
        .options(
            joinedload(VehicleSighting.event).joinedload(DetectionEvent.plate_read),
            joinedload(VehicleSighting.camera),
        )
        .filter(VehicleSighting.vehicle_id == v.id)
        .order_by(VehicleSighting.timestamp)
        .all()
    )
    return VehicleDetail(vehicle=VehicleOut.model_validate(v), sightings=[_sighting_out(s) for s in sightings])


@router.get("/{vehicle_id}/timeline")
def vehicle_timeline(vehicle_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Chronological camera sequence for a vehicle (only recorded sightings)."""
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")
    rows = (
        db.query(VehicleSighting, Camera)
        .join(Camera, VehicleSighting.camera_id == Camera.id)
        .filter(VehicleSighting.vehicle_id == v.id)
        .order_by(VehicleSighting.timestamp)
        .all()
    )
    seq = [
        {
            "camera_id": c.id,
            "camera_name": c.name,
            "location": c.location_name,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "timestamp": s.timestamp.isoformat(),
        }
        for s, c in rows
    ]
    return {
        "registration_number": v.registration_number,
        "total_sightings": len(seq),
        "first_seen": seq[0]["timestamp"] if seq else None,
        "last_seen": seq[-1]["timestamp"] if seq else None,
        "camera_sequence": seq,
        "note": "Sequence shows only cameras where the vehicle was actually recorded; no unobserved path is implied.",
    }
