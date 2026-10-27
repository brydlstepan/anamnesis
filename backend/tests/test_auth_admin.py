import pytest
from fastapi.testclient import TestClient

from anamnesis.config import Settings
from anamnesis.main import create_app

from .conftest import CSRF


def test_health_and_meta(app):
    with TestClient(app) as c:
        assert c.get("/api/v1/health").json() == {"status": "ok"}
        meta = c.get("/api/v1/meta").json()
        assert meta["admin_path"] == "/admin"
        assert meta["oidc_enabled"] is False


def test_security_headers_and_csrf(app):
    with TestClient(app) as c:
        r = c.get("/api/v1/health")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        # unsafe method without CSRF header is rejected
        r = c.post("/api/v1/auth/login", json={"email": "a@b.c", "password": "x"})
        assert r.status_code == 403


def test_unauthenticated_access_denied(app):
    with TestClient(app) as c:
        assert c.get("/api/v1/auth/me").status_code == 401
        assert c.get("/api/v1/persons").status_code == 401
        assert c.get("/api/admin/users").status_code == 401


def test_admin_login_wrong_password_and_rate_limit(app):
    with TestClient(app, headers=CSRF) as c:
        for _ in range(10):
            assert c.post("/api/admin/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
        assert c.post("/api/admin/auth/login", json={"username": "admin", "password": "nope"}).status_code == 429


def test_admin_cannot_access_user_api(admin_client):
    assert admin_client.get("/api/v1/persons").status_code == 401


def test_admin_user_lifecycle(admin_client, make_user, settings):
    alice = make_user("alice@example.com")
    users = admin_client.get("/api/admin/users").json()
    assert [u["email"] for u in users] == ["alice@example.com"]
    uid = users[0]["id"]
    # duplicate
    r = admin_client.post("/api/admin/users", json={"email": "ALICE@example.com", "password": "x" * 12})
    assert r.status_code == 409
    # weak password
    r = admin_client.post("/api/admin/users", json={"email": "bob@example.com", "password": "short"})
    assert r.status_code == 422
    # disable -> session no longer valid
    assert admin_client.patch(f"/api/admin/users/{uid}", json={"is_active": False}).status_code == 200
    assert alice.get("/api/v1/auth/me").status_code == 401
    # delete requires confirmation
    assert admin_client.delete(f"/api/admin/users/{uid}", params={"confirm_email": "x@y.z"}).status_code == 422
    assert admin_client.delete(f"/api/admin/users/{uid}", params={"confirm_email": "alice@example.com"}).status_code == 204
    assert admin_client.get("/api/admin/users").json() == []
    audit = admin_client.get("/api/admin/audit").json()
    assert {"user.create", "user.disable", "user.delete"} <= {e["action"] for e in audit}


def test_user_login_logout_and_password_change(make_user, app):
    alice = make_user("alice@example.com")
    me = alice.get("/api/v1/auth/me").json()
    assert me["email"] == "alice@example.com" and me["person_id"]
    r = alice.post("/api/v1/auth/me/password", json={"current_password": "wrong", "new_password": "n" * 12})
    assert r.status_code == 400
    r = alice.post(
        "/api/v1/auth/me/password", json={"current_password": "user-password-123", "new_password": "new-password-456"}
    )
    assert r.status_code == 204
    assert alice.post("/api/v1/auth/logout").status_code == 204
    assert alice.get("/api/v1/auth/me").status_code == 401
    with TestClient(app, headers=CSRF) as c:
        bad = c.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "user-password-123"})
        assert bad.status_code == 401
        ok = c.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "new-password-456"})
        assert ok.status_code == 200


def test_settings(admin_client, make_user):
    s = admin_client.get("/api/admin/settings").json()
    assert s["user_directory_enabled"] is False and s["default_language"] == "cs"
    alice = make_user("alice@example.com")
    make_user("bob@example.com")
    assert alice.get("/api/v1/users/directory").status_code == 403
    admin_client.put("/api/admin/settings", json={"user_directory_enabled": True, "default_language": "en"})
    found = alice.get("/api/v1/users/directory", params={"q": "bob"}).json()
    assert [u["email"] for u in found] == ["bob@example.com"]
    assert alice.get("/api/v1/meta").json()["default_language"] == "en"


def test_weak_admin_env_password_refuses_start(tmp_path):
    s = Settings(secret_key="k" * 40, admin_password="short", data_dir=tmp_path)
    with pytest.raises(RuntimeError), TestClient(create_app(s)):
        pass


def test_admin_password_rotation_from_env(tmp_path):
    base = {"secret_key": "k" * 40, "data_dir": tmp_path}
    with TestClient(create_app(Settings(**base, admin_password="first-password-1")), headers=CSRF):
        pass
    with TestClient(create_app(Settings(**base, admin_password="second-password-2")), headers=CSRF) as c:
        assert c.post("/api/admin/auth/login", json={"username": "admin", "password": "first-password-1"}).status_code == 401
        assert c.post("/api/admin/auth/login", json={"username": "admin", "password": "second-password-2"}).status_code == 200


def test_invalid_admin_path_rejected():
    with pytest.raises(ValueError):
        Settings(secret_key="k" * 40, admin_path="/api/x")
