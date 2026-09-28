"""System health endpoints."""
from datetime import timedelta

import psutil
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, engine
from app.core.security import get_current_user, require_admin
from app.models.system import AuditLog, SystemHealth
from app.models.user import User, utcnow
from app.services.detection_service import detector, plate_reader
from app.workers.spooler import spooler

router = APIRouter(tags=["health"])


def _check_database() -> tuple[str, str]:
    try:
        with engine.connect() as conn:
            from sqlalchemy import text

            conn.execute(text("SELECT 1"))
        return "online", ""
    except Exception as exc:
        return "error", str(exc)[:200]


@router.get("/health", response_model=list)
def health(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_status, db_detail = _check_database()
    proc = psutil.Process()
    components = [
        {
            "component": "api",
            "status": "online",
            "detail": f"pid={proc.pid}",
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "memory_percent": proc.memory_percent(),
            "checked_at": utcnow().isoformat(),
        },
        {
            "component": "database",
            "status": db_status,
            "detail": db_detail or settings.DATABASE_URL.split("://")[0],
            "cpu_percent": 0,
            "memory_percent": 0,
            "checked_at": utcnow().isoformat(),
        },
        {
            "component": "ingestion_worker",
            "status": "online" if spooler.running else ("degraded" if not spooler.camera_states else "offline"),
            "detail": f"{spooler.active_count()} active source(s)",
            "cpu_percent": 0,
            "memory_percent": 0,
            "checked_at": utcnow().isoformat(),
        },
        {
            "component": "ai_detection",
            "status": "online" if detector.available else "degraded",
            "detail": (f"YOLO on {detector.device}" if detector.available else detector.load_error or "ultralytics/torch not installed — running in degraded mode"),
            "cpu_percent": 0,
            "memory_percent": 0,
            "checked_at": utcnow().isoformat(),
        },
        {
            "component": "anpr_ocr",
            "status": "online" if plate_reader.available else "degraded",
            "detail": ("PaddleOCR ready" if plate_reader.available else plate_reader.load_error or "paddleocr not installed — ANPR disabled"),
            "cpu_percent": 0,
            "memory_percent": 0,
            "checked_at": utcnow().isoformat(),
        },
    ]
    # persist latest snapshot (best effort)
    try:
        for c in components:
            row = db.query(SystemHealth).filter(SystemHealth.component == c["component"]).first()
            if row is None:
                row = SystemHealth(component=c["component"])
                db.add(row)
            row.status = c["status"]
            row.detail = c["detail"]
            row.checked_at = utcnow()
        db.commit()
    except Exception:
        db.rollback()
    return components


@router.get("/audit-logs")
def audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action.like(f"%{action}%"))
    total = q.count()
    rows = q.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "username": r.username,
                "action": r.action,
                "resource": r.resource,
                "detail": r.detail,
                "ip_address": r.ip_address,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
