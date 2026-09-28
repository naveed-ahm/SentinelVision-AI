"""Pytest fixtures."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_sentinelvision.db"
os.environ["SECRET_KEY"] = "test_secret_key_not_for_production"
os.environ["ENVIRONMENT"] = "development"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    import app.models  # noqa: F401 — register all tables
    from app.core.database import Base, engine
    from app.seed import seed
    import os as _os

    if _os.path.exists("./test_sentinelvision.db"):
        _os.remove("./test_sentinelvision.db")
    Base.metadata.create_all(bind=engine)
    seed(force=True)  # demo users + labeled synthetic data for tests
    yield
    try:
        _os.remove("./test_sentinelvision.db")
    except OSError:
        pass


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_headers(client):
    r = client.post("/api/v1/auth/login", data={"username": "admin", "password": "Admin@12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def operator_headers(client):
    r = client.post("/api/v1/auth/login", data={"username": "operator", "password": "Operator@12345"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def viewer_headers(client):
    r = client.post("/api/v1/auth/login", data={"username": "viewer", "password": "Viewer@12345"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
