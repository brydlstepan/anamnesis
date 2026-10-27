"""OIDC callback logic with a fake OAuth client (no network)."""

from fastapi.testclient import TestClient

from anamnesis.config import Settings
from anamnesis.main import create_app

from .conftest import CSRF


class FakeClient:
    def __init__(self, claims):
        self.claims = claims

    async def authorize_access_token(self, request):
        return {"userinfo": self.claims}


class FakeOAuth:
    def __init__(self, claims):
        self.oidc = FakeClient(claims)


def _login(app, claims) -> tuple[TestClient, str]:
    app.state.oauth = FakeOAuth(claims)
    c = TestClient(app, headers=CSRF, follow_redirects=False)
    c.__enter__()
    r = c.get("/api/v1/auth/oidc/callback")
    return c, r.headers["location"]


def test_oidc_settings_enable_flag(tmp_path):
    s = Settings(secret_key="k" * 40, data_dir=tmp_path, oidc_issuer="https://idp.example",
                 oidc_client_id="anamnesis", oidc_client_secret="secret")
    with TestClient(create_app(s)) as c:
        assert c.get("/api/v1/meta").json()["oidc_enabled"] is True


def test_oidc_provisioning_and_pending_share(app, make_user):
    alice = make_user("alice@example.com")
    apid = alice.me["person_id"]
    alice.post(f"/api/v1/persons/{apid}/shares", json={"email": "erin@example.com", "role": "viewer"})

    c, loc = _login(app, {"sub": "idp-erin", "email": "Erin@Example.com", "email_verified": True, "name": "Erin"})
    assert loc == "/"
    me = c.get("/api/v1/auth/me").json()
    assert me["email"] == "erin@example.com" and me["auth_provider"] == "oidc" and me["display_name"] == "Erin"
    assert {p["id"] for p in c.get("/api/v1/persons").json()} >= {apid}
    # local password login is not possible for OIDC accounts
    r = c.post("/api/v1/auth/login", json={"email": "erin@example.com", "password": "anything-long-enough"})
    assert r.status_code == 401

    # second login with same subject reuses the account
    c2, _ = _login(app, {"sub": "idp-erin", "email": "erin@example.com"})
    assert c2.get("/api/v1/auth/me").json()["id"] == me["id"]


def test_oidc_rejections(app):
    _, loc = _login(app, {"sub": "x", "email": "x@example.com", "email_verified": False})
    assert "login_error=email" in loc
    _, loc = _login(app, {"sub": "x"})
    assert "login_error=email" in loc
    _login(app, {"sub": "s1", "email": "same@example.com"})
    _, loc = _login(app, {"sub": "s2", "email": "same@example.com"})
    assert "login_error=subject" in loc


def test_oidc_disabled_user(app, admin_client):
    c, _ = _login(app, {"sub": "d1", "email": "dis@example.com"})
    uid = c.get("/api/v1/auth/me").json()["id"]
    admin_client.patch(f"/api/admin/users/{uid}", json={"is_active": False})
    _, loc = _login(app, {"sub": "d1", "email": "dis@example.com"})
    assert "login_error=disabled" in loc
