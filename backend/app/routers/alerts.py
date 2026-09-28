"""Alert management endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_current_user, require_operator
from app.models.alert import Alert
from app.models.user import User
from app.schemas.schemas import AlertOut, AlertPage
from app.services.audit import audit

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertPage)
def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(open|acknowledged|resolved)$"),
    severity: str | None = Query(None, pattern="^(info|warning|critical)$"),
    alert_type: str | None = None,
    camera_id: int | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = db.query(Alert).options(joinedload(Alert.camera))
    if status:
        q = q.filter(Alert.status == status)
    if severity:
        q = q.filter(Alert.severity == severity)
    if alert_type:
        q = q.filter(Alert.alert_type == alert_type)
    if camera_id:
        q = q.filter(Alert.camera_id == camera_id)
    total = q.count()
    items = q.order_by(Alert.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return AlertPage(
        items=[AlertOut.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
    request: Request = None,
):
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    if a.status == "open":
        a.status = "acknowledged"
        a.acknowledged_by = user.id
        a.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(a)
        audit(db, request, user, "alert.acknowledge", str(a.id))
    return a


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
    request: Request = None,
):
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    a.status = "resolved"
    if not a.acknowledged_by:
        a.acknowledged_by = user.id
        a.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(a)
    audit(db, request, user, "alert.resolve", str(a.id))
    return a


@router.post("/{alert_id}/assign", response_model=AlertOut)
def assign(
    alert_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
    request: Request = None,
):
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    a.assigned_to = user_id
    db.commit()
    db.refresh(a)
    audit(db, request, user, "alert.assign", str(a.id), f"to={user_id}")
    return a
