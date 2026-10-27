import pytest
from fastapi.testclient import TestClient

from anamnesis.config import Settings
from anamnesis.main import create_app

ADMIN_PW = "admin-password-123"
CSRF = {"X-Requested-With": "anamnesis"}


@pytest.fixture
def settings(tmp_path):
    return Settings(
        secret_key="test-secret-key-" + "x" * 32,
        admin_username="admin",
        admin_password=ADMIN_PW,
        data_dir=tmp_path / "data",
        public_url="http://testserver",
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


def _client(app) -> TestClient:
    c = TestClient(app)
    c.headers.update(CSRF)
    return c


@pytest.fixture
def admin_client(app):
    with _client(app) as c:
        r = c.post("/api/admin/auth/login", json={"username": "admin", "password": ADMIN_PW})
        assert r.status_code == 200, r.text
        yield c


@pytest.fixture
def make_user(app, admin_client):
    """Creates a local user via admin API and returns a logged-in client for them."""
    clients: list[TestClient] = []

    def _make(email: str, password: str = "user-password-123") -> TestClient:
        r = admin_client.post("/api/admin/users", json={"email": email, "password": password, "display_name": email})
        assert r.status_code == 201, r.text
        c = _client(app)
        c.__enter__()
        clients.append(c)
        r = c.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        c.me = r.json()
        return c

    yield _make
    for c in clients:
        c.__exit__(None, None, None)
