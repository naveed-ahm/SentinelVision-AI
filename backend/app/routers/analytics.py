"""Analytics endpoints powering the Overview dashboard charts."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.event import DetectionEvent, PlateRead, Vehicle
from app.models.user import User
from app.schemas.schemas import (
    AlertTypeBreakdown,
    CameraAvailability,
    ClassBreakdown,
    OverviewStats,
    TimeSeriesPoint,
)
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=OverviewStats)
def overview(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.workers.live_store import live_store

    return analytics_service.overview_stats(db, streams_active=len(live_store.fresh_codes()))


@router.get("/detections-series", response_model=list[TimeSeriesPoint])
def detections_series(
    hours: int = Query(24, ge=1, le=168),
    buckets: int = Query(24, ge=6, le=96),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return analytics_service.detections_series(db, hours=hours, buckets=buckets)


@router.get("/class-breakdown", response_model=list[ClassBreakdown])
def class_breakdown(hours: int = Query(24, ge=1, le=168), _user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analytics_service.class_breakdown(db, hours=hours)


@router.get("/camera-availability", response_model=list[CameraAvailability])
def camera_availability(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analytics_service.camera_availability(db)


@router.get("/alert-breakdown", response_model=list[AlertTypeBreakdown])
def alert_breakdown(days: int = Query(7, ge=1, le=30), _user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analytics_service.alert_type_breakdown(db, days=days)


@router.get("/recent-detections", response_model=list[dict])
def recent_detections(limit: int = Query(10, ge=1, le=50), _user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(DetectionEvent)
        .options(joinedload(DetectionEvent.camera), joinedload(DetectionEvent.plate_read))
        .order_by(DetectionEvent.timestamp.desc())
        .limit(limit)
        .all()
    )
    out = []
    for e in rows:
        pr = e.plate_read
        out.append(
            {
                "id": e.id,
                "camera_id": e.camera_id,
                "camera_name": e.camera.name if e.camera else None,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "object_class": e.object_class,
                "confidence": e.confidence,
                "image_path": e.image_path,
                "plate_text": (pr.corrected_text or pr.plate_text) if pr else None,
                "ocr_confidence": pr.ocr_confidence if pr else None,
                "is_demo": e.is_demo,
            }
        )
    return out
