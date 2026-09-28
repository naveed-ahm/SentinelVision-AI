"""Optional AI module endpoints (status + attribute/re-id/person/quality/anomaly queries).

New endpoints ONLY — existing routers, paths and behaviors are untouched.
All require authentication like the rest of the API.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.ai_modules import (
    AnomalyReview,
    PersonDetection,
    QualityMetric,
    ReidMatch,
    VehicleAttribute,
)
from app.models.camera import Camera
from app.models.event import DetectionEvent
from app.models.user import User
from app.schemas.schemas import (
    AiModulesStatus,
    AnomalyReviewOut,
    PersonDetectionOut,
    QualityMetricOut,
    ReidMatchOut,
    VehicleAttributeOut,
)
from app.services.person_service import person_detector
from app.services.quality_service import quality_assessor
from app.services.anomaly_service import anomaly_engine
from app.services.reid_service import reid_engine

router = APIRouter(prefix="/ai-modules", tags=["ai-modules"])


def _camera_name(db: Session, camera_id: int | None) -> str | None:
    if camera_id is None:
        return None
    name = db.query(Camera.name).filter(Camera.id == camera_id).scalar()
    return name


@router.get("/status", response_model=AiModulesStatus)
def modules_status(_user: User = Depends(get_current_user)):
    """Aggregate availability of the optional modules.

    The heuristic engines (reid/quality/anomaly) are dependency-free, so their
    lazy load() is safe to trigger here. The person model is NOT loaded from
    the API process — its availability reflects whether it has already been
    loaded in this process (the ingestion worker loads its own instance).
    """
    reid_engine.load()
    quality_assessor.load()
    anomaly_engine.load()
    return AiModulesStatus(
        reid={
            "enabled": settings.ENABLE_REID,
            "available": reid_engine.available,
            "gallery_size": reid_engine.gallery_size(),
            "mode": "unconfirmed-matches",
        },
        attributes={
            "enabled": settings.ENABLE_ATTRIBUTES,
            "available": True,  # heuristic tier has no external deps
            "mode": "heuristic-hsv",
        },
        person={
            "enabled": settings.ENABLE_PERSON_MODEL,
            **person_detector.status(),
        },
        quality={
            "enabled": settings.ENABLE_QUALITY,
            "available": quality_assessor.available,
            "sample_every_n": settings.QUALITY_SAMPLE_EVERY_N,
        },
        anomaly={
            "enabled": settings.ENABLE_ANOMALY,
            "available": anomaly_engine.available,
            **anomaly_engine.status(),
        },
    )


@router.get("/attributes", response_model=list[VehicleAttributeOut])
def list_attributes(
    camera_id: int | None = None,
    color: str | None = None,
    vehicle_type: str | None = None,
    event_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(VehicleAttribute).options(joinedload(VehicleAttribute.camera))
    if camera_id:
        q = q.filter(VehicleAttribute.camera_id == camera_id)
    if color:
        q = q.filter(VehicleAttribute.color == color.lower())
    if vehicle_type:
        q = q.filter(VehicleAttribute.vehicle_type == vehicle_type)
    if event_id:
        q = q.filter(VehicleAttribute.event_id == event_id)
    return q.order_by(VehicleAttribute.timestamp.desc()).limit(limit).all()


@router.get("/reid-matches", response_model=list[ReidMatchOut])
def list_reid_matches(
    camera_id: int | None = None,
    status: str | None = None,
    min_similarity: float = Query(None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(ReidMatch)
    if camera_id:
        q = q.filter(ReidMatch.camera_id == camera_id)
    if status:
        q = q.filter(ReidMatch.status == status)
    if min_similarity is not None:
        q = q.filter(ReidMatch.similarity >= min_similarity)
    return q.order_by(ReidMatch.created_at.desc()).limit(limit).all()


@router.post("/reid-matches/{match_id}/confirm")
def confirm_reid_match(
    match_id: int,
    decision: str = Query(..., pattern="^(confirmed|rejected)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Human decision on an appearance match. Appearance alone is never proof."""
    m = db.get(ReidMatch, match_id)
    if not m:
        raise HTTPException(404, "Re-ID match not found")
    m.status = decision
    db.commit()
    return {"id": m.id, "status": m.status}


@router.get("/quality", response_model=list[QualityMetricOut])
def list_quality(
    camera_id: int | None = None,
    verdict: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(QualityMetric)
    if camera_id:
        q = q.filter(QualityMetric.camera_id == camera_id)
    if verdict:
        q = q.filter(QualityMetric.verdict == verdict)
    return q.order_by(QualityMetric.timestamp.desc()).limit(limit).all()


@router.get("/quality/summary")
def quality_summary(
    camera_id: int | None = None,
    hours: int = Query(24, ge=1, le=168),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per-camera mean quality scores for the trailing window."""
    from datetime import datetime, timedelta, timezone

    from app.models.user import utcnow

    start = utcnow() - timedelta(hours=hours)
    q = db.query(
        QualityMetric.camera_id,
        func.count(QualityMetric.id),
        func.avg(QualityMetric.composite),
        func.avg(QualityMetric.blur_score),
        func.avg(QualityMetric.brightness_score),
        func.avg(QualityMetric.visibility_score),
    ).filter(QualityMetric.timestamp >= start)
    if camera_id:
        q = q.filter(QualityMetric.camera_id == camera_id)
    rows = q.group_by(QualityMetric.camera_id).all()
    out = []
    for cid, n, comp, blur, bright, vis in rows:
        cam = db.get(Camera, cid)
        out.append(
            {
                "camera_id": cid,
                "camera_name": cam.name if cam else f"Camera #{cid}",
                "samples": n or 0,
                "avg_composite": round(float(comp), 3) if comp is not None else None,
                "avg_blur": round(float(blur), 3) if blur is not None else None,
                "avg_brightness": round(float(bright), 3) if bright is not None else None,
                "avg_visibility": round(float(vis), 3) if vis is not None else None,
            }
        )
    return {"hours": hours, "cameras": out}


@router.get("/persons", response_model=list[PersonDetectionOut])
def list_person_detections(
    camera_id: int | None = None,
    min_confidence: float = Query(None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(PersonDetection).options(joinedload(PersonDetection.camera))
    if camera_id:
        q = q.filter(PersonDetection.camera_id == camera_id)
    if min_confidence is not None:
        q = q.filter(PersonDetection.confidence >= min_confidence)
    return q.order_by(PersonDetection.timestamp.desc()).limit(limit).all()


@router.get("/anomalies", response_model=list[AnomalyReviewOut])
def list_anomalies(
    camera_id: int | None = None,
    anomaly_type: str | None = None,
    review_status: str | None = Query(None, pattern="^(pending|reviewed)$"),
    limit: int = Query(50, ge=1, le=200),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(AnomalyReview).options(joinedload(AnomalyReview.camera))
    if camera_id:
        q = q.filter(AnomalyReview.camera_id == camera_id)
    if anomaly_type:
        q = q.filter(AnomalyReview.anomaly_type == anomaly_type)
    if review_status:
        q = q.filter(AnomalyReview.review_status == review_status)
    return q.order_by(AnomalyReview.timestamp.desc()).limit(limit).all()


@router.post("/anomalies/{review_id}/review")
def review_anomaly(
    review_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark an anomaly review as handled (human-in-the-loop)."""
    r = db.get(AnomalyReview, review_id)
    if not r:
        raise HTTPException(404, "Anomaly review not found")
    r.review_status = "reviewed"
    r.reviewed_by = user.id
    db.commit()
    return {"id": r.id, "review_status": r.review_status}


@router.get("/events/{event_id}/attributes", response_model=list[VehicleAttributeOut])
def attributes_for_event(
    event_id: int,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(VehicleAttribute).filter(VehicleAttribute.event_id == event_id).all()


@router.get("/attributes/recent-by-vehicle")
def attributes_recent_by_vehicle(
    limit: int = Query(30, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Latest attribute row per recently-tracked vehicle, mapped by vehicle_id.

    One batched query so the Tracking page can enrich cards with a single
    request. Read-only join across existing tables + the new attribute table.
    """
    from app.models.event import VehicleSighting

    rows = (
        db.query(VehicleSighting.vehicle_id, VehicleAttribute)
        .join(DetectionEvent, VehicleSighting.event_id == DetectionEvent.id)
        .join(VehicleAttribute, VehicleAttribute.event_id == DetectionEvent.id)
        .order_by(VehicleSighting.timestamp.desc())
        .limit(limit * 4)
        .all()
    )
    latest: dict[int, VehicleAttribute] = {}
    for vehicle_id, attr in rows:
        if vehicle_id not in latest:
            latest[vehicle_id] = attr
    return {
        str(vid): {
            "vehicle_type": a.vehicle_type,
            "color": a.color,
            "body_style": a.body_style,
            "color_confidence": a.color_confidence,
        }
        for vid, a in list(latest.items())[:limit]
    }
