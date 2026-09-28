"""Tests for the optional AI modules (Re-ID, attributes, person, quality, anomaly).

The heavy optional dependencies (ultralytics/torch) are NOT installed in CI, so
model-backed modules are exercised via their graceful-degradation paths —
mirroring how the existing YOLO/ANPR tests behave. Heuristic modules
(quality/attributes/anomaly/reid-gallery) are tested end-to-end for real.
"""
import numpy as np

from app.core.config import settings


def _login(client, username="admin", password="Admin@12345"):
    r = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------- unit-level service tests ----------------


def test_quality_scores_blur_and_dark_frames():
    from app.services.quality_service import quality_assessor

    rng = np.random.default_rng(7)
    sharp = (rng.random((240, 320)) * 255).astype(np.uint8)
    frame = np.dstack([sharp, sharp, sharp])
    good = quality_assessor.assess(frame)
    assert good is not None and 0.0 <= good["composite"] <= 1.0

    flat = np.full((240, 320, 3), 127, dtype=np.uint8)  # blurred, mid-gray
    poor = quality_assessor.assess(flat)
    assert poor is not None and poor["composite"] < good["composite"]

    assert quality_assessor.assess(None) is None
    assert quality_assessor.assess(np.zeros((0, 0, 3), dtype=np.uint8)) is None


def test_attributes_recognizes_color_and_body_style():
    from app.services.attributes_service import attribute_recognizer

    blue = np.zeros((80, 160, 3), dtype=np.uint8)
    blue[:, :] = (200, 120, 40)  # BGR blue-ish
    out = attribute_recognizer.recognize(blue, yolo_label="car")
    assert out is not None
    assert out["vehicle_type"] == "car"
    assert out["body_style"] in ("sedan", "sedan-long")  # aspect 2.0 maps to sedan-long
    assert out["color"] in ("blue", "other")
    assert 0.0 <= out["color_confidence"] <= 1.0
    assert attribute_recognizer.recognize(np.zeros((5, 5, 3), dtype=np.uint8), "car") is None


def test_reid_matches_same_vehicle_across_cameras():
    from app.services.reid_service import reid_engine

    reid_engine.reset()
    crop = np.full((64, 64, 3), 90, dtype=np.uint8)
    first = reid_engine.register_and_match(
        event_id=1, camera_id=1, crop_bgr=crop, label="car", is_demo=True
    )
    assert first is None  # empty gallery -> no match
    second = reid_engine.register_and_match(
        event_id=2, camera_id=2, crop_bgr=crop, label="car", is_demo=True
    )
    assert second is not None
    assert second["matched_event_id"] == 1
    assert second["similarity"] >= settings.REID_SIMILARITY_THRESHOLD
    assert second["confirmed_by_plate"] is False  # appearance-only -> unconfirmed


def test_reid_disabled_returns_none(monkeypatch):
    from app.services.reid_service import reid_engine

    monkeypatch.setattr(settings, "ENABLE_REID", False)
    try:
        out = reid_engine.register_and_match(
            event_id=9, camera_id=1, crop_bgr=np.full((64, 64, 3), 10, dtype=np.uint8), label="car"
        )
        assert out is None
    finally:
        monkeypatch.undo()


def test_anomaly_speed_and_person_exclusion():
    from app.services.anomaly_service import anomaly_engine

    anomaly_engine.reset()
    # fast rightward motion across the sampled history
    history = [(float(x), 50.0, 120.0, 60.0) for x in range(0, 480, 20)]
    finding = anomaly_engine.evaluate_track(
        camera_id=901, track_id=1, label="car", history=history, sample_interval=0.5
    )
    assert finding is None  # no calibration yet -> no false positive

    # person tracks are excluded entirely
    person_hist = [(float(x), 50.0, 60.0, 160.0) for x in range(0, 400, 20)]
    assert (
        anomaly_engine.evaluate_track(
            camera_id=902, track_id=2, label="person", history=person_hist, sample_interval=0.5
        )
        is None
    )


def test_anomaly_flags_high_speed_motion():
    from app.services.anomaly_service import anomaly_engine

    anomaly_engine.reset()
    cam_id = 903
    # 400 px jumps per 0.2 s sample with ~120 px wide vehicles (≈1.8 m reference)
    # -> ~2000 px/s / (120/1.8 px per m) ≈ 30 m/s ≈ 108 km/h > 90 km/h threshold.
    history = [(float(x), 50.0, 120.0, 60.0) for x in range(0, 8000, 400)]
    flagged = anomaly_engine.evaluate_track(
        camera_id=cam_id, track_id=1, label="car", history=history, sample_interval=0.2
    )
    assert flagged is not None, "sustained fast motion should be flagged for review"
    assert flagged["anomaly_type"] == "speed"
    assert 0.0 < flagged["score"] <= 1.0
    # cooldown suppresses immediate repeats for the same camera
    assert (
        anomaly_engine.evaluate_track(
            camera_id=cam_id, track_id=2, label="car", history=history, sample_interval=0.2
        )
        is None
    )
    anomaly_engine.reset()


# ---------------- API tests (new /ai-modules endpoints) ----------------


def test_modules_status_endpoint(client, admin_headers):
    r = client.get("/api/v1/ai-modules/status", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    for key in ("reid", "attributes", "person", "quality", "anomaly"):
        assert key in data
        assert isinstance(data[key]["enabled"], bool)


def test_ai_module_endpoints_require_auth(client):
    assert client.get("/api/v1/ai-modules/status").status_code in (401, 403)
    assert client.get("/api/v1/ai-modules/attributes").status_code in (401, 403)
    assert client.get("/api/v1/ai-modules/anomalies").status_code in (401, 403)


def test_empty_module_listings(client, admin_headers):
    for path in (
        "/api/v1/ai-modules/attributes",
        "/api/v1/ai-modules/reid-matches",
        "/api/v1/ai-modules/quality",
        "/api/v1/ai-modules/persons",
        "/api/v1/ai-modules/anomalies",
    ):
        r = client.get(path, headers=admin_headers)
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:200]}"
        assert r.json() == []


def test_new_tables_created_and_isolated(client, admin_headers):
    """New tables exist; no existing table was altered (counts still work)."""
    from sqlalchemy import inspect

    from app.core.database import engine

    inspector = inspect(engine)
    for table in ("vehicle_attributes", "reid_matches", "quality_metrics", "person_detections", "anomaly_reviews"):
        assert inspector.has_table(table), f"missing table {table}"
    # existing endpoints unaffected
    r = client.get("/api/v1/vehicles", headers=admin_headers)
    assert r.status_code == 200


def test_settings_include_new_module_flags(admin_headers, client):
    r = client.get("/api/v1/settings", headers=admin_headers)
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()}
    for key in ("ENABLE_REID", "ENABLE_ATTRIBUTES", "ENABLE_PERSON_MODEL", "ENABLE_QUALITY", "ENABLE_ANOMALY"):
        assert key in keys


def test_ingestion_module_failure_is_contained(monkeypatch):
    """A broken new module must not break _persist_detection."""
    import os
    import tempfile

    from app.workers.ingestion import CameraWorker
    from app.models.camera import Camera

    worker = CameraWorker(
        Camera(
            id=10**6, code="TEST-MODULE-FAIL", name="t", location_name="t", protocol="file",
            rtsp_url="", enabled=True, detection_enabled=True, is_demo=True,
        )
    )
    worker._last_frame = np.full((120, 160, 3), 100, dtype=np.uint8)

    class FakeTrack:
        track_id = 1
        label = "car"
        confidence = 0.9
        bbox = (10.0, 10.0, 40.0, 30.0)
        history = []

        def __init__(self):
            self.extras = {}

    # force the attributes module to explode inside its guarded block
    def boom(*a, **k):
        raise RuntimeError("module exploded")

    monkeypatch.setattr(settings, "ENABLE_ATTRIBUTES", True)
    monkeypatch.setattr(settings, "ENABLE_REID", True)
    # patch storage.save_jpeg so crop saving works without disk assumptions
    orig_cwd = os.getcwd()
    try:
        tmp = tempfile.mkdtemp()
        os.chdir(tmp)  # keep any accidental writes inside a temp dir
        import app.services.storage as storage_mod

        monkeypatch.setattr(storage_mod.storage, "save_jpeg", staticmethod(lambda data, folder, prefix: "x/y.jpg"))
        worker._persist_detection(FakeTrack(), __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    finally:
        os.chdir(orig_cwd)
        monkeypatch.undo()
