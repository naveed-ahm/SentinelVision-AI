"""Aggregation helpers for stats, time series and breakdowns (SQL-level)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.camera import Camera
from app.models.event import DetectionEvent, PlateRead, Vehicle, VehicleSighting
from app.models.user import utcnow


def overview_stats(db: Session, streams_active: int) -> dict:
    now = utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    cams = db.query(Camera).all()
    return {
        "cameras_total": len(cams),
        "cameras_online": sum(1 for c in cams if c.status == "online"),
        "cameras_offline": sum(1 for c in cams if c.status != "online"),
        "streams_active": streams_active,
        "detections_today": db.query(DetectionEvent)
        .filter(DetectionEvent.timestamp >= day_start)
        .count(),
        "anpr_today": db.query(PlateRead).filter(PlateRead.created_at >= day_start).count(),
        "alerts_open": db.query(Alert).filter(Alert.status == "open").count(),
        "events_total": db.query(DetectionEvent).count(),
        "demo_mode": True,
    }


def detections_series(db: Session, hours: int = 24, buckets: int = 24) -> list[dict]:
    """Hourly vehicle-detection counts for the trailing window."""
    now = utcnow()
    start = now - timedelta(hours=hours)
    rows = (
        db.query(DetectionEvent.timestamp, DetectionEvent.object_class)
        .filter(
            DetectionEvent.timestamp >= start,
            DetectionEvent.object_class.in_(["car", "motorcycle", "bus", "truck"]),
        )
        .all()
    )
    width = hours * 3600 / buckets
    series = [0] * buckets
    for ts, _cls in rows:
        ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        offset = (ts - start).total_seconds()
        idx = min(int(offset // width), buckets - 1)
        if idx >= 0:
            series[idx] += 1
    out = []
    for i, count in enumerate(series):
        bucket_start = start + timedelta(seconds=width * i)
        out.append({"bucket": bucket_start.isoformat(), "count": count})
    return out


def class_breakdown(db: Session, hours: int = 24) -> list[dict]:
    start = utcnow() - timedelta(hours=hours)
    rows = (
        db.query(DetectionEvent.object_class, func.count(DetectionEvent.id))
        .filter(DetectionEvent.timestamp >= start)
        .group_by(DetectionEvent.object_class)
        .all()
    )
    return [{"object_class": cls, "count": n} for cls, n in rows]


def camera_availability(db: Session) -> list[dict]:
    cams = db.query(Camera).order_by(Camera.name).all()
    return [
        {"camera_id": c.id, "name": c.name, "status": c.status, "uptime_pct": 100.0 if c.status == "online" else 0.0}
    for c in cams
    ]


def alert_type_breakdown(db: Session, days: int = 7) -> list[dict]:
    start = utcnow() - timedelta(days=days)
    rows = (
        db.query(Alert.alert_type, Alert.severity, func.count(Alert.id))
        .filter(Alert.created_at >= start)
        .group_by(Alert.alert_type, Alert.severity)
        .all()
    )
    return [{"alert_type": t, "severity": s, "count": n} for t, s, n in rows]


def vehicle_summary(db: Session, limit: int = 10) -> list[Vehicle]:
    return (
        db.query(Vehicle)
        .order_by(Vehicle.last_seen_at.desc())
        .limit(limit)
        .all()
    )


def anpr_review_queue(db: Session, limit: int = 50):
    return (
        db.query(PlateRead)
        .filter(PlateRead.needs_review.is_(True))
        .order_by(PlateRead.created_at.desc())
        .limit(limit)
        .all()
    )
