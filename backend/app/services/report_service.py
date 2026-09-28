"""Report generation (CSV) from actual recorded data."""
import csv
import io
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.camera import Camera
from app.models.event import DetectionEvent, PlateRead, Vehicle, VehicleSighting
from app.models.user import utcnow


def _fmt(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


def build_csv_report(db: Session, start: datetime, end: datetime, title: str) -> tuple[str, str]:
    """Returns (filename, csv_content). Only real rows from the database."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    start_s, end_s = start.isoformat(), end.isoformat()

    events = (
        db.query(DetectionEvent)
        .filter(DetectionEvent.timestamp >= start, DetectionEvent.timestamp <= end)
        .order_by(DetectionEvent.timestamp)
        .all()
    )
    plates = (
        db.query(PlateRead)
        .filter(PlateRead.created_at >= start, PlateRead.created_at <= end)
        .count()
    )
    alerts = (
        db.query(Alert)
        .filter(Alert.created_at >= start, Alert.created_at <= end)
        .order_by(Alert.created_at)
        .all()
    )
    cams = db.query(Camera).all()

    writer.writerow([f"SentinelVision AI Report — {title}"])
    writer.writerow(["Period (UTC)", start_s, "to", end_s])
    writer.writerow(["Generated (UTC)", utcnow().isoformat()])
    writer.writerow([])
    writer.writerow(["Summary", ""])
    writer.writerow(["Total detections", len(events)])
    writer.writerow(["Plate reads", plates])
    writer.writerow(["Alerts", len(alerts)])
    writer.writerow(["Registered cameras", len(cams)])
    writer.writerow([])
    writer.writerow(["Camera summary", ""])
    writer.writerow(["ID", "Code", "Name", "Status", "Location", "Demo data"])
    for c in cams:
        writer.writerow([c.id, c.code, c.name, c.status, c.location_name, "yes" if c.is_demo else "no"])
    writer.writerow([])
    writer.writerow(["Vehicle detections", ""])
    writer.writerow(["Event ID", "Timestamp (UTC)", "Camera", "Class", "Confidence", "Track ID", "Image"])
    for e in events:
        cam = next((c for c in cams if c.id == e.camera_id), None)
        writer.writerow(
            [e.id, _fmt(e.timestamp), cam.code if cam else e.camera_id, e.object_class,
             f"{e.confidence:.3f}", e.track_id or "", e.image_path]
        )
    writer.writerow([])
    writer.writerow(["Alerts", ""])
    writer.writerow(["Alert ID", "Timestamp (UTC)", "Type", "Severity", "Camera", "Title", "Status"])
    for a in alerts:
        cam = next((c for c in cams if c.id == a.camera_id), None)
        writer.writerow(
            [a.id, _fmt(a.created_at), a.alert_type, a.severity, cam.code if cam else "",
             a.title, a.status]
        )
    writer.writerow([])
    writer.writerow(["Top vehicles by sightings", ""])
    writer.writerow(["Registration", "Class", "First seen", "Last seen", "Sightings"])
    for v in (
        db.query(Vehicle)
        .filter(Vehicle.last_seen_at >= start, Vehicle.first_seen_at <= end)
        .order_by(Vehicle.total_sightings.desc())
        .limit(20)
        .all()
    ):
        writer.writerow([v.registration_number, v.vehicle_class, _fmt(v.first_seen_at), _fmt(v.last_seen_at), v.total_sightings])

    stamp = utcnow().strftime("%Y%m%d_%H%M%S")
    return f"sentinelvision_report_{stamp}.csv", buf.getvalue()


def delete_old_media(db: Session, days: int) -> int:  # pragma: no cover - retention helper
    cutoff = utcnow() - timedelta(days=days)
    ids = [
        row[0]
        for row in db.query(DetectionEvent.id).filter(DetectionEvent.timestamp < cutoff).all()
    ]
    return len(ids)
