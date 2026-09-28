"""Watchlist module tests: CRUD + RBAC, normalization, matching, hit recording, isolation."""
from datetime import timedelta

from app.core.config import settings
from app.models.user import utcnow


def _login(client, username="admin", password="Admin@12345"):
    r = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------- unit tests ----------------


def test_normalize_plate_strips_separators_keeps_case_distinctions():
    from app.services.watchlist_service import normalize_plate

    assert normalize_plate("gj01ab1234") == "GJ01AB1234"
    assert normalize_plate("GJ-01 AB 1234") == "GJ01AB1234"  # separators stripped
    assert normalize_plate("  *GJ!01@AB#1234*  ") == "GJ01AB1234"
    assert normalize_plate("GJO1AB1234") == "GJO1AB1234"  # letter O preserved (no risky folding)
    assert normalize_plate("") == ""


# ---------------- API + RBAC ----------------


def test_create_list_update_delete_entry(client, admin_headers):
    payload = {
        "category": "stolen_vehicle",
        "identifier_value": "GJ11XX9911",
        "title": "Test stolen vehicle",
        "severity": "critical",
        "notes": "pytest entry",
    }
    r = client.post("/api/v1/watchlist", json=payload, headers=admin_headers)
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["identifier_value"] == "GJ11XX9911"
    assert entry["active"] is True and entry["is_demo"] is False

    # duplicate rejected
    r2 = client.post("/api/v1/watchlist", json=payload, headers=admin_headers)
    assert r2.status_code == 409

    # list + filter
    r3 = client.get("/api/v1/watchlist", params={"q": "XX99"}, headers=admin_headers)
    assert r3.status_code == 200
    assert any(e["id"] == entry["id"] for e in r3.json())

    # update
    r4 = client.patch(f"/api/v1/watchlist/{entry['id']}", json={"active": False, "severity": "info"}, headers=admin_headers)
    assert r4.status_code == 200
    assert r4.json()["active"] is False and r4.json()["severity"] == "info"

    # delete
    r5 = client.delete(f"/api/v1/watchlist/{entry['id']}", headers=admin_headers)
    assert r5.status_code == 204
    assert client.get("/api/v1/watchlist/check/GJ11XX9911", headers=admin_headers).json()["on_watchlist"] is False


def test_viewer_cannot_modify_watchlist(client, viewer_headers, admin_headers):
    r = client.post("/api/v1/watchlist", json={"identifier_value": "GJ22VV2211"}, headers=viewer_headers)
    assert r.status_code == 403
    # viewer can read
    assert client.get("/api/v1/watchlist", headers=viewer_headers).status_code == 200
    # cleanup any operator-created leftovers from other tests
    items = client.get("/api/v1/watchlist", params={"q": "VV22"}, headers=admin_headers).json()
    for e in items:
        client.delete(f"/api/v1/watchlist/{e['id']}", headers=admin_headers)


def test_check_endpoint_lookup_only(client, admin_headers):
    client.post("/api/v1/watchlist", json={"identifier_value": "GJ33TT3311", "category": "blacklist"}, headers=admin_headers)
    r = client.get("/api/v1/watchlist/check/gj-33-tt-3311", headers=admin_headers)
    body = r.json()
    assert body["on_watchlist"] is True
    assert body["plate"] == "GJ33TT3311"
    assert body["entries"][0]["category"] == "blacklist"
    for e in client.get("/api/v1/watchlist", params={"q": "TT33"}, headers=admin_headers).json():
        client.delete(f"/api/v1/watchlist/{e['id']}", headers=admin_headers)


# ---------------- matching service ----------------


def test_check_plate_records_hit_and_alert(db_session=None):
    from app.core.database import SessionLocal
    from app.models.camera import Camera
    from app.services.watchlist_service import watchlist_service

    db = SessionLocal()
    try:
        entry = __import__("app.models.watchlist", fromlist=["WatchlistEntry"]).WatchlistEntry(
            category="stolen_vehicle",
            identifier_type="plate",
            identifier_value="GJ44RR4411",
            display_value="GJ44RR4411",
            title="pytest stolen",
            severity="critical",
            active=True,
        )
        db.add(entry)
        cam = db.query(Camera).first()
        db.commit()

        hit = watchlist_service.check_plate(
            db,
            plate_text="GJ-44-RR-4411",
            ocr_confidence=0.9,
            camera_id=cam.id if cam else None,
            camera_name="pytest cam",
        )
        assert hit is not None
        assert hit.plate_text == "GJ44RR4411"
        assert hit.alert_id is not None  # alert created + linked

        # below confidence -> no hit
        hit2 = watchlist_service.check_plate(
            db, plate_text="GJ44RR4411", ocr_confidence=settings.WATCHLIST_MATCH_MIN_CONFIDENCE - 0.05
        )
        assert hit2 is None

        # expired entry -> no hit
        entry.expires_at = utcnow() - timedelta(hours=1)
        db.commit()
        hit3 = watchlist_service.check_plate(db, plate_text="GJ44RR4411", ocr_confidence=0.9)
        assert hit3 is None

        # cleanup
        db.query(__import__("app.models.watchlist", fromlist=["WatchlistHit"]).WatchlistHit).filter(
            __import__("app.models.watchlist", fromlist=["WatchlistHit"]).WatchlistHit.entry_id == entry.id
        ).delete()
        db.delete(entry)
        db.commit()
    finally:
        db.close()


def test_watchlist_failure_is_contained(monkeypatch):
    """If the DB check explodes, check_plate returns None instead of raising."""
    from app.core.database import SessionLocal
    from app.services.watchlist_service import watchlist_service

    class Boom:
        def query(self, *a, **k):
            raise RuntimeError("db exploded")

    db = SessionLocal()
    try:
        monkeypatch.setattr(db, "query", Boom().query)
        out = watchlist_service.check_plate(db, plate_text="GJ01AB1234", ocr_confidence=0.9)
        assert out is None
    finally:
        monkeypatch.undo()
        db.close()


def test_hits_endpoint_shape(client, admin_headers):
    r = client.get("/api/v1/watchlist/hits", headers=admin_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_settings_expose_watchlist_keys(client, admin_headers):
    keys = {s["key"] for s in client.get("/api/v1/settings", headers=admin_headers).json()}
    assert "ENABLE_WATCHLIST" in keys and "WATCHLIST_MATCH_MIN_CONFIDENCE" in keys
