"""API tests: auth, RBAC, cameras, events, alerts, vehicles, analytics, settings, reports."""
import time

from app.core.security import hash_password
from app.models.user import User


def _login(client, username, password):
    r = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------- Auth ----------------


def test_login_success(client):
    r = client.post("/api/v1/auth/login", data={"username": "admin", "password": "Admin@12345"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["role"] == "admin"


def test_login_wrong_password(client):
    r = client.post("/api/v1/auth/login", data={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    r = client.get("/api/v1/auth/me", headers=_login(client, "viewer", "Viewer@12345"))
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"


def test_invalid_token_rejected(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


# ---------------- RBAC ----------------


def test_viewer_cannot_create_camera(client, viewer_headers):
    r = client.post(
        "/api/v1/cameras",
        json={"name": "X", "code": "XYZ-1"},
        headers=viewer_headers,
    )
    assert r.status_code == 403


def test_viewer_cannot_acknowledge_alerts(client, viewer_headers, admin_headers):
    # create an alert via camera offline flow is complex; use existing seeded alerts
    r = client.get("/api/v1/alerts", headers=admin_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    if items:
        alert_id = items[0]["id"]
        r = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=viewer_headers)
        assert r.status_code == 403


def test_operator_can_create_camera_but_not_users(client, operator_headers):
    r = client.post(
        "/api/v1/cameras",
        json={"name": "Op Camera", "code": "OP-1", "protocol": "file"},
        headers=operator_headers,
    )
    assert r.status_code == 201
    r = client.post(
        "/api/v1/users",
        json={"username": "hacker", "email": "h@x.local", "password": "Password@1"},
        headers=operator_headers,
    )
    assert r.status_code == 403


# ---------------- Cameras ----------------


def test_camera_crud_and_credential_redaction(client, admin_headers):
    r = client.post(
        "/api/v1/cameras",
        json={
            "name": "Gate Camera",
            "code": "GATE-1",
            "protocol": "rtsp",
            "rtsp_url": "rtsp://user:supersecret@10.0.0.9:554/stream1",
            "credential": {"username": "user", "secret": "supersecret"},
        },
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    cam = r.json()
    cam_id = cam["id"]
    assert "supersecret" not in r.text  # credential never echoed
    assert "***" in cam["rtsp_url"]

    r = client.get("/api/v1/cameras", headers=admin_headers)
    assert all("supersecret" not in item["rtsp_url"] for item in r.json())

    r = client.patch(f"/api/v1/cameras/{cam_id}", json={"name": "Gate Camera v2"}, headers=admin_headers)
    assert r.json()["name"] == "Gate Camera v2"

    r = client.post(f"/api/v1/cameras/{cam_id}/test", headers=admin_headers)
    assert r.status_code == 200 and r.json()["ok"] is False  # unreachable host, handled gracefully

    r = client.delete(f"/api/v1/cameras/{cam_id}", headers=admin_headers)
    assert r.status_code == 204
    assert client.get(f"/api/v1/cameras/{cam_id}", headers=admin_headers).status_code == 404


def test_camera_duplicate_code_rejected(client, admin_headers):
    payload = {"name": "Dup", "code": "DUP-1", "protocol": "file"}
    assert client.post("/api/v1/cameras", json=payload, headers=admin_headers).status_code == 201
    assert client.post("/api/v1/cameras", json=payload, headers=admin_headers).status_code == 409


def test_camera_filters(client, admin_headers):
    r = client.get("/api/v1/cameras", params={"search": "Gate"}, headers=admin_headers)
    assert r.status_code == 200
    assert all("Gate" in c["name"] or "Gate" in c["location_name"] for c in r.json())


# ---------------- Events / Vehicles ----------------


def test_events_pagination(client, admin_headers):
    r = client.get("/api/v1/events", params={"page": 1, "page_size": 5}, headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["page_size"] == 5
    assert len(body["items"]) <= 5


def test_event_filters_and_structure(client, admin_headers):
    r = client.get("/api/v1/events", params={"object_class": "car"}, headers=admin_headers)
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["object_class"] == "car"


def test_vehicle_search(client, admin_headers):
    r = client.get("/api/v1/vehicles", params={"registration_number": "GJ01"}, headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert all("GJ01" in v["registration_number"] for v in body["items"])


def test_vehicle_detail_timeline(client, admin_headers):
    r = client.get("/api/v1/vehicles", headers=admin_headers)
    items = r.json()["items"]
    if items:
        vid = items[0]["id"]
        d = client.get(f"/api/v1/vehicles/{vid}", headers=admin_headers)
        assert d.status_code == 200
        assert "sightings" in d.json()
        t = client.get(f"/api/v1/vehicles/{vid}/timeline", headers=admin_headers)
        assert t.status_code == 200
        assert "note" in t.json()


# ---------------- Alerts ----------------


def test_alert_flow(client, admin_headers):
    r = client.get("/api/v1/alerts", params={"status": "open"}, headers=admin_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    if items:
        aid = items[0]["id"]
        r2 = client.post(f"/api/v1/alerts/{aid}/acknowledge", headers=admin_headers)
        assert r2.status_code == 200
        assert r2.json()["status"] == "acknowledged"
        r3 = client.post(f"/api/v1/alerts/{aid}/resolve", headers=admin_headers)
        assert r3.json()["status"] == "resolved"


def test_alert_severity_filter(client, admin_headers):
    r = client.get("/api/v1/alerts", params={"severity": "warning"}, headers=admin_headers)
    assert all(a["severity"] == "warning" for a in r.json()["items"])


# ---------------- Analytics / GIS / Reports ----------------


def test_overview_stats(client, admin_headers):
    r = client.get("/api/v1/analytics/overview", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["cameras_total"] >= 1
    assert body["demo_mode"] is True


def test_charts_endpoints(client, admin_headers):
    for ep in ("detections-series", "class-breakdown", "camera-availability", "alert-breakdown"):
        r = client.get(f"/api/v1/analytics/{ep}", headers=admin_headers)
        assert r.status_code == 200


def test_gis_cameras_and_sightings(client, admin_headers):
    r = client.get("/api/v1/gis/cameras", headers=admin_headers)
    assert r.status_code == 200
    cams = r.json()
    demo = [c for c in cams if c["code"].startswith("DEMO-")]
    assert demo and all(c["latitude"] is not None and c["longitude"] is not None for c in demo)
    r = client.get("/api/v1/gis/sightings", headers=admin_headers)
    assert r.status_code == 200


def test_csv_report(client, operator_headers):
    r = client.get(
        "/api/v1/reports/csv",
        params={"start": "2020-01-01T00:00:00", "end": "2030-01-01T00:00:00", "title": "Test report"},
        headers=operator_headers,
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    body = r.text
    assert "SentinelVision AI Report" in body


def test_csv_report_viewer_forbidden(client, viewer_headers):
    r = client.get(
        "/api/v1/reports/csv",
        params={"start": "2020-01-01T00:00:00", "end": "2030-01-01T00:00:00"},
        headers=viewer_headers,
    )
    assert r.status_code == 403


# ---------------- Settings / Health ----------------


def test_settings_admin_only_write(client, viewer_headers, admin_headers):
    assert client.get("/api/v1/settings", headers=admin_headers).status_code == 200
    r = client.put("/api/v1/settings/DETECTION_CONFIDENCE", json={"value": "0.4"}, headers=admin_headers)
    assert r.status_code == 200
    r = client.put("/api/v1/settings/DETECTION_CONFIDENCE", json={"value": "0.4"}, headers=viewer_headers)
    assert r.status_code == 403
    r = client.put("/api/v1/settings/FORBIDDEN_KEY", json={"value": "1"}, headers=admin_headers)
    assert r.status_code == 400


def test_health_endpoint(client, admin_headers):
    r = client.get("/api/v1/health", headers=admin_headers)
    assert r.status_code == 200
    comps = {c["component"] for c in r.json()}
    assert {"api", "database", "ai_detection"} <= comps


def test_validation_error(client, admin_headers):
    r = client.post("/api/v1/cameras", json={"name": "", "code": "bad code with spaces"}, headers=admin_headers)
    assert r.status_code == 422


def test_openapi_available(client):
    r = client.get("/docs")
    assert r.status_code == 200
