"""GIS endpoints: cameras + vehicle sightings mapped to coordinates."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.camera import Camera
from app.models.event import DetectionEvent, PlateRead, Vehicle, VehicleSighting
from app.models.user import User
from app.schemas.schemas import GisCamera, GisPathPoint, GisSighting

router = APIRouter(prefix="/gis", tags=["gis"])


@router.get("/cameras", response_model=list[GisCamera])
def gis_cameras(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Camera).order_by(Camera.name).all()


@router.get("/sightings", response_model=list[GisSighting])
def gis_sightings(
    registration_number: str | None = None,
    camera_id: int | None = None,
    vehicle_class: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(500, ge=1, le=2000),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sighting points for the map. Only sightings whose camera has coordinates."""
    q = (
        db.query(VehicleSighting)
        .join(Camera, VehicleSighting.camera_id == Camera.id)
        .options(
            joinedload(VehicleSighting.event).joinedload(DetectionEvent.plate_read),
            joinedload(VehicleSighting.camera),
            joinedload(VehicleSighting.vehicle),
        )
        .filter(Camera.latitude.is_not(None), Camera.longitude.is_not(None))
    )
    if registration_number:
        q = q.filter(Vehicle.registration_number.like(f"%{registration_number.upper()}%"))
    if camera_id:
        q = q.filter(VehicleSighting.camera_id == camera_id)
    if vehicle_class:
        q = q.filter(DetectionEvent.object_class == vehicle_class)
    if start:
        q = q.filter(VehicleSighting.timestamp >= start)
    if end:
        q = q.filter(VehicleSighting.timestamp <= end)

    rows = q.order_by(VehicleSighting.timestamp.desc()).limit(limit).all()
    out = []
    for s in rows:
        cam = s.camera
        e = s.event
        pr = e.plate_read if e else None
        out.append(
            GisSighting(
                event_id=s.event_id,
                camera_id=s.camera_id,
                camera_name=cam.name,
                latitude=cam.latitude,
                longitude=cam.longitude,
                timestamp=s.timestamp,
                registration_number=(pr.corrected_text or pr.plate_text) if pr else None,
                object_class=e.object_class if e else None,
                confidence=e.confidence if e else None,
                image_path=e.image_path if e else "",
            )
        )
    return out


@router.get("/paths/{vehicle_id}", response_model=GisPathPoint)
def gis_path(
    vehicle_id: int,
    min_points: int = Query(2, ge=2, le=10),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Movement polyline for one vehicle. Returned only when there are at
    least `min_points` geolocated sightings; no fictional route is generated."""
    v = db.get(Vehicle, vehicle_id)
    if not v:
        from fastapi import HTTPException

        raise HTTPException(404, "Vehicle not found")
    rows = (
        db.query(VehicleSighting)
        .join(Camera, VehicleSighting.camera_id == Camera.id)
        .options(joinedload(VehicleSighting.event).joinedload(DetectionEvent.plate_read), joinedload(VehicleSighting.camera))
        .filter(VehicleSighting.vehicle_id == vehicle_id, Camera.latitude.is_not(None), Camera.longitude.is_not(None))
        .order_by(VehicleSighting.timestamp)
        .all()
    )
    points = [
        GisSighting(
            event_id=s.event_id,
            camera_id=s.camera_id,
            camera_name=s.camera.name,
            latitude=s.camera.latitude,
            longitude=s.camera.longitude,
            timestamp=s.timestamp,
            registration_number=(s.event.plate_read.corrected_text or s.event.plate_read.plate_text)
            if s.event and s.event.plate_read
            else None,
            object_class=s.event.object_class if s.event else None,
            confidence=s.event.confidence if s.event else None,
            image_path=s.event.image_path if s.event else "",
        )
        for s in rows
    ]
    return GisPathPoint(registration_number=v.registration_number, points=points)
