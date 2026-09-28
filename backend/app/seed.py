"""Seed the database with demo users, cameras and clearly-labeled demo data.

Run:  python -m app.seed          (from backend/)
"""
from __future__ import annotations

import random
from datetime import timedelta, timezone

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.alert import Alert
from app.models.camera import Camera
from app.models.event import DetectionEvent, PlateRead, Vehicle, VehicleSighting
from app.models.system import AuditLog
from app.models.user import User, utcnow
from app.models.watchlist import WatchlistEntry

# Representative demo watchlist entries (first two plates appear in the
# synthetic 24h history above, so the demo shows live matches immediately).
DEMO_WATCHLIST = [
    dict(identifier="GJ01AB1234", category="stolen_vehicle", title="Stolen sedan — Ahmedabad FIR #142/2026",
         notes="REPRESENTATIVE DEMO RECORD for hackathon demonstration — not a real stolen vehicle.", severity="critical"),
    dict(identifier="GJ05CD5678", category="blacklist", title="Blacklisted vehicle — inter-state watch",
         notes="REPRESENTATIVE DEMO RECORD for hackathon demonstration.", severity="warning"),
    dict(identifier="GJ99ZZ9999", category="wanted_person", title="Wanted person — associated vehicle",
         notes="REPRESENTATIVE DEMO RECORD for hackathon demonstration.", severity="critical"),
]

PLATES = [
    "GJ01AB1234", "GJ05CD5678", "GJ18EF9012", "GJ27GH3456",
    "MH12KL7890", "DL8CAF4567", "GJ03MN2345", "GJ22PQ6789",
]
CLASSES = ["car", "car", "car", "motorcycle", "bus", "truck"]

DEMO_CAMERAS = [
    dict(code="DEMO-SG-001", name="SG Highway — Trial Overpass", location_name="SG Highway, Ahmedabad", lat=23.0225, lng=72.5714,
         rtsp_url="../data/demo_videos/demo_traffic.mp4"),
    dict(code="DEMO-CT-002", name="CG Road — Ellis Bridge End", location_name="CG Road, Ahmedabad", lat=23.0246, lng=72.5636,
         rtsp_url="../data/demo_videos/demo_city.mp4"),
    dict(code="DEMO-MN-003", name="Maninagar Station Entrance", location_name="Maninagar, Ahmedabad", lat=23.0226, lng=72.5850,
         rtsp_url="../data/demo_videos/demo_station.mp4"),
    dict(code="DEMO-RS-004", name="Ring Road — Narol Circle", location_name="Ring Road, Ahmedabad", lat=22.9901, lng=72.5834,
         rtsp_url="../data/demo_videos/demo_ring.mp4"),
    dict(code="DEMO-UP-005", name="University Road Junction", location_name="Navrangpura, Ahmedabad", lat=23.0330, lng=72.5499,
         rtsp_url="../data/demo_videos/demo_campus.mp4"),
    dict(code="DEMO-KB-006", name="Kankaria Lake Approach", location_name="Kankaria, Ahmedabad", lat=23.0080, lng=72.5920,
         rtsp_url="../data/demo_videos/demo_lake.mp4"),
]


def seed(force: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # --- demo watchlist entries (clearly labeled representative data) ---
        # Runs even when the DB is already seeded (idempotent), so existing
        # deployments gain the demo watchlist on the next seed run.
        for spec in DEMO_WATCHLIST:
            normalized = spec["identifier"].upper()
            if not db.query(WatchlistEntry).filter(WatchlistEntry.identifier_value == normalized).first():
                db.add(
                    WatchlistEntry(
                        category=spec["category"],
                        identifier_type="plate",
                        identifier_value=normalized,
                        display_value=spec["identifier"],
                        title=spec["title"],
                        notes=spec["notes"],
                        severity=spec["severity"],
                        active=True,
                        is_demo=True,
                    )
                )
        db.commit()

        if not force and db.query(User).first():
            print("Database already seeded — skipping (use --force to reseed).")
            return

        # --- users ---
        if not db.query(User).filter(User.username == "admin").first():
            db.add_all(
                [
                    User(username="admin", email="admin@sentinelvision.local", full_name="System Administrator",
                         role="admin", hashed_password=hash_password("Admin@12345"), is_active=True),
                    User(username="operator", email="operator@sentinelvision.local", full_name="Control Room Operator",
                         role="operator", hashed_password=hash_password("Operator@12345"), is_active=True),
                    User(username="viewer", email="viewer@sentinelvision.local", full_name="Read-only Viewer",
                         role="viewer", hashed_password=hash_password("Viewer@12345"), is_active=True),
                ]
            )
            db.commit()

        # --- cameras (demo, synthetic metadata) ---
        cams = []
        for spec in DEMO_CAMERAS:
            cam = db.query(Camera).filter(Camera.code == spec["code"]).first()
            if not cam:
                cam = Camera(
                    name=spec["name"],
                    code=spec["code"],
                    location_name=spec["location_name"],
                    latitude=spec["lat"],
                    longitude=spec["lng"],
                    manufacturer="Demo Vendor",
                    model="SV-POC-100",
                    protocol="file",
                    rtsp_url=spec.get("rtsp_url", ""),
                    description="DEMONSTRATION camera with synthetic metadata. Attach a local video via Settings to see live video.",
                    enabled=True,
                    detection_enabled=True,
                    is_demo=True,
                )
                db.add(cam)
                db.flush()
            cams.append(cam)
        db.commit()

        if not force and db.query(DetectionEvent).first():
            print("Demo events already present — skipping synthetic history.")
            return

        # --- synthetic detection history (labeled is_demo=True everywhere) ---
        now = utcnow()
        rng = random.Random(42)
        for hours_ago in range(23, -1, -1):
            base_ts = now - timedelta(hours=hours_ago)
            for cam in rng.sample(cams, k=rng.randint(3, 5)):
                for _ in range(rng.randint(2, 7)):
                    ts = base_ts + timedelta(minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
                    cls = rng.choice(CLASSES)
                    plate = rng.choice(PLATES) if rng.random() < 0.55 else ""
                    conf = round(rng.uniform(0.55, 0.97), 3)
                    needs_review = conf < settings.OCR_MIN_CONFIDENCE
                    pr = None
                    if plate:
                        pr = PlateRead(
                            plate_text=plate,
                            raw_text=plate,
                            ocr_confidence=conf if not needs_review else round(conf * 0.7, 3),
                            needs_review=needs_review,
                            is_demo=True,
                            created_at=ts,
                        )
                        db.add(pr)
                        db.flush()
                    ev = DetectionEvent(
                        camera_id=cam.id,
                        timestamp=ts,
                        object_class=cls,
                        confidence=conf,
                        bbox_x=rng.uniform(10, 400), bbox_y=rng.uniform(10, 240),
                        bbox_w=rng.uniform(60, 160), bbox_h=rng.uniform(50, 120),
                        track_id=rng.randint(1, 500),
                        is_demo=True,
                        plate_read_id=pr.id if pr else None,
                    )
                    db.add(ev)
                    db.flush()
                    if pr and not needs_review:
                        vehicle = db.query(Vehicle).filter(Vehicle.registration_number == plate).first()
                        if not vehicle:
                            vehicle = Vehicle(registration_number=plate, vehicle_class=cls, is_demo=True,
                                              first_seen_at=ts)
                            db.add(vehicle)
                            db.flush()
                        vehicle.total_sightings += 1
                        last = vehicle.last_seen_at
                        if last is None:
                            vehicle.last_seen_at = ts
                        else:
                            last = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
                            if ts > last:
                                vehicle.last_seen_at = ts
                        db.add(VehicleSighting(vehicle_id=vehicle.id, event_id=ev.id, camera_id=cam.id, timestamp=ts))
        db.commit()

        # --- alerts derived from that history ---
        alert_specs = [
            ("camera_offline", "warning", "Camera offline: Ring Road — Narol Circle",
             "DEMO-RS-004 stopped producing frames for more than 3 minutes.", 4),
            ("camera_online", "info", "Camera restored: Ring Road — Narol Circle",
             "DEMO-RS-004 is streaming again.", 3),
            ("unreadable_plate", "info", "Unreadable plate on CG Road — Ellis Bridge End",
             "OCR returned partial text; manual review required.", 2),
            ("repeated_vehicle", "info", "Vehicle GJ01AB1234 reached 20 sightings",
             "High-frequency sighting across demo cameras in the last 24h.", 1),
        ]
        for atype, sev, title, desc, hours in alert_specs:
            db.add(Alert(
                alert_type=atype, severity=sev, camera_id=cams[3].id if atype.startswith("camera") else None,
                title=title, description=desc, is_demo=True,
                created_at=now - timedelta(hours=hours),
                status="open" if sev == "warning" else "open",
            ))
        db.commit()

        db.add(AuditLog(username="system", action="seed.demo", resource="database", detail="Synthetic demo data generated"))
        db.commit()
        print("Seed complete: 3 users, %d demo cameras, synthetic 24h history." % len(cams))
        print("  admin / Admin@12345   (administrator)")
        print("  operator / Operator@12345")
        print("  viewer / Viewer@12345")
        print("All seeded records are labeled is_demo=true and shown as DEMO DATA in the UI.")
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    seed(force="--force" in sys.argv)
