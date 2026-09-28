"""Detection-event history and plate-read review endpoints."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_current_user, require_operator
from app.models.alert import Alert
from app.models.event import DetectionEvent, PlateRead, Vehicle, VehicleSighting
from app.models.user import User, utcnow
from app.schemas.schemas import DetectionEventOut, EventPage, PlateCorrection, PlateReadOut
from app.services.alert_service import raise_alert

router = APIRouter(tags=["events"])


@router.get("/events", response_model=EventPage)
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    camera_id: int | None = None,
    object_class: str | None = None,
    plate_text: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = db.query(DetectionEvent).options(joinedload(DetectionEvent.plate_read), joinedload(DetectionEvent.camera))
    if camera_id:
        q = q.filter(DetectionEvent.camera_id == camera_id)
    if object_class:
        q = q.filter(DetectionEvent.object_class == object_class)
    if plate_text:
        like = f"%{plate_text.upper()}%"
        q = q.join(PlateRead, DetectionEvent.plate_read_id == PlateRead.id).filter(
            PlateRead.plate_text.like(like) | PlateRead.corrected_text.like(like)
        )
    if start:
        q = q.filter(DetectionEvent.timestamp >= start)
    if end:
        q = q.filter(DetectionEvent.timestamp <= end)

    total = q.count()
    items = (
        q.order_by(DetectionEvent.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return EventPage(
        items=[DetectionEventOut.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/events/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    e = (
        db.query(DetectionEvent)
        .options(
            joinedload(DetectionEvent.plate_read),
            joinedload(DetectionEvent.camera),
            joinedload(DetectionEvent.sighting).joinedload(VehicleSighting.vehicle),
        )
        .filter(DetectionEvent.id == event_id)
        .first()
    )
    if not e:
        raise HTTPException(404, "Event not found")
    cam = e.camera
    pr = e.plate_read
    sighting = e.sighting
    vehicle = sighting.vehicle if sighting else None
    return {
        "event": DetectionEventOut.model_validate(e).model_dump(mode="json"),
        "camera": {"id": cam.id, "name": cam.name, "code": cam.code, "location_name": cam.location_name} if cam else None,
        "plate_read": PlateReadOut.model_validate(pr).model_dump(mode="json") if pr else None,
        "vehicle": {"id": vehicle.id, "registration_number": vehicle.registration_number} if vehicle else None,
    }


@router.get("/plate-reads", response_model=list[PlateReadOut])
def list_plate_reads(
    needs_review: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = db.query(PlateRead)
    if needs_review is not None:
        q = q.filter(PlateRead.needs_review.is_(needs_review))
    return q.order_by(PlateRead.created_at.desc()).limit(limit).all()


@router.post("/plate-reads/{plate_read_id}/correct", response_model=PlateReadOut)
def correct_plate_read(
    plate_read_id: int,
    payload: PlateCorrection,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    """Manual correction of an uncertain ANPR result (authorized operators)."""
    pr = db.get(PlateRead, plate_read_id)
    if not pr:
        raise HTTPException(404, "Plate read not found")
    corrected = payload.corrected_text.upper().strip()
    pr.corrected_text = corrected
    pr.corrected_by = user.id
    pr.needs_review = False
    db.commit()
    db.refresh(pr)

    # If a sighting was created from this read, move it to the right vehicle.
    event = db.query(DetectionEvent).filter(DetectionEvent.plate_read_id == pr.id).first()
    sighting = (
        db.query(VehicleSighting).filter(VehicleSighting.event_id == event.id).first() if event else None
    )
    if sighting:
        old_vehicle = sighting.vehicle
        if old_vehicle:
            old_vehicle.total_sightings = max(0, old_vehicle.total_sightings - 1)
            if old_vehicle.total_sightings == 0:
                db.delete(old_vehicle)
        veh = db.query(Vehicle).filter(Vehicle.registration_number == corrected).first()
        if not veh:
            veh = Vehicle(registration_number=corrected, vehicle_class=event.object_class, is_demo=pr.is_demo)
            db.add(veh)
            db.flush()
        sighting.vehicle_id = veh.id
        veh.total_sightings += 1
        veh.last_seen_at = max(veh.last_seen_at, sighting.timestamp) if veh.last_seen_at else sighting.timestamp
        db.commit()
    return pr


@router.get("/alerts/{alert_id}")
def alert_detail(alert_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    return {
        "id": a.id,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "camera_id": a.camera_id,
        "event_id": a.event_id,
        "title": a.title,
        "description": a.description,
        "status": a.status,
        "acknowledged_by": a.acknowledged_by,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "is_demo": a.is_demo,
    }
