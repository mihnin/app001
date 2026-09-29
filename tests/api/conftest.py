import pytest
from fastapi.testclient import TestClient

from app.clock import FixedClock
from app.config import Settings
from app.main import create_app
from tests.factories import msk


@pytest.fixture
def clock():
    return FixedClock(msk(10, 0))


@pytest.fixture
def app(tmp_path, clock):
    settings = Settings(db_path=str(tmp_path / "api.db"), staff_password="secret-pass")
    return create_app(settings=settings, clock=clock)


@pytest.fixture
def guest(app):
    return TestClient(app)


@pytest.fixture
def guest2(app):
    return TestClient(app)


@pytest.fixture
def staff(app):
    client = TestClient(app)
    r = client.post("/api/staff/login", json={"password": "secret-pass"})
    assert r.status_code == 200
    return client
