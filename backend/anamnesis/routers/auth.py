"""User authentication: local login, OIDC (auto-provisioning), current user (SPEC §3.3)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import __version__
from ..config import SUPPORTED_LANGUAGES
from ..db import get_db
from ..deps import SESSION_USER, audit, client_ip, current_user, get_app_setting, get_settings
from ..ids import utcnow
from ..models import User
from ..security import hash_password, password_problem, verify_password
from ..users import activate_pending_shares, create_user, normalize_email, own_person

log = logging.getLogger("anamnesis.auth")
router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/meta")
def meta(request: Request, db: Session = Depends(get_db)) -> dict:
    s = get_settings(request)
    return {
        "name": "Anamnesis",
        "version": __version__,
        "admin_path": s.admin_path,
        "oidc_enabled": s.oidc_enabled,
        "oidc_display_name": s.oidc_display_name,
        "default_language": get_app_setting(db, "default_language") or s.default_language,
        "languages": list(SUPPORTED_LANGUAGES),
    }


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


def _user_out(db: Session, user: User) -> dict:
    person = own_person(db, user)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "auth_provider": user.auth_provider,
        "language": user.language,
        "show_access_log": user.show_access_log,
        "person_id": person.id if person else None,
    }


def _start_session(request: Request, db: Session, user: User) -> None:
    request.session.clear()  # avoid fixation / mixing with an admin session
    request.session[SESSION_USER] = user.id
    user.last_login_at = utcnow()
    activate_pending_shares(db, user)
    audit(db, request, action="auth.login", actor=user)
    db.commit()


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> dict:
    limiter = request.app.state.rate_limiter
    key = f"user:{client_ip(request)}:{body.email.strip().lower()}"
    if not limiter.allowed(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, try again later")
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    ok = verify_password(user.password_hash if user else None, body.password)
    if not (ok and user and user.is_active and user.auth_provider == "local"):
        limiter.fail(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    limiter.reset(key)
    _start_session(request, db, user)
    return _user_out(db, user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request) -> None:
    request.session.pop(SESSION_USER, None)


@router.get("/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return _user_out(db, user)


class MeUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=200)
    language: str | None = None
    show_access_log: bool | None = None


@router.patch("/auth/me")
def update_me(body: MeUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if body.display_name is not None and body.display_name.strip():
        user.display_name = body.display_name.strip()
    if body.language is not None:
        if body.language not in SUPPORTED_LANGUAGES:
            raise HTTPException(422, f"language must be one of {SUPPORTED_LANGUAGES}")
        user.language = body.language
    if body.show_access_log is not None:
        user.show_access_log = body.show_access_log
    db.commit()
    return _user_out(db, user)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(max_length=1024)


@router.post("/auth/me/password", status_code=204)
def change_password(
    body: PasswordChange, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    if user.auth_provider != "local":
        raise HTTPException(400, "Password is managed by your identity provider")
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(400, "Current password is incorrect")
    if problem := password_problem(body.new_password):
        raise HTTPException(422, problem)
    user.password_hash = hash_password(body.new_password)
    audit(db, request, action="auth.password_change", actor=user)
    db.commit()


# ---------------------------------------------------------------- OIDC


def _oauth_client(request: Request):
    oauth = request.app.state.oauth
    if oauth is None:
        raise HTTPException(404, "OIDC is not configured")
    return oauth.oidc


@router.get("/auth/oidc/login")
async def oidc_login(request: Request):
    client = _oauth_client(request)
    redirect_uri = f"{get_settings(request).public_url}/api/v1/auth/oidc/callback"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/auth/oidc/callback")
async def oidc_callback(request: Request, db: Session = Depends(get_db)):
    from authlib.integrations.starlette_client import OAuthError

    client = _oauth_client(request)
    try:
        token = await client.authorize_access_token(request)
        claims = token.get("userinfo") or await client.userinfo(token=token)
    except OAuthError as e:
        log.warning("OIDC callback failed: %s", e)
        return RedirectResponse("/?login_error=oidc", status_code=302)

    email_raw = claims.get("email")
    if not email_raw or claims.get("email_verified") is False:
        return RedirectResponse("/?login_error=email", status_code=302)
    try:
        email = normalize_email(email_raw)
    except ValueError:
        return RedirectResponse("/?login_error=email", status_code=302)
    subject = str(claims.get("sub") or "")

    user = db.scalar(select(User).where(User.oidc_subject == subject)) if subject else None
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is not None and user.oidc_subject and user.oidc_subject != subject:
            log.warning("OIDC subject mismatch for %s", email)
            return RedirectResponse("/?login_error=subject", status_code=302)
    if user is None:
        # Auto-provision (Q12). Access control is delegated to the IdP's allow-list (Q20).
        user = create_user(
            db,
            email=email,
            provider="oidc",
            display_name=str(claims.get("name") or claims.get("preferred_username") or ""),
            oidc_subject=subject or None,
        )
        audit(db, request, action="user.provisioned", actor=user)
    elif not user.oidc_subject and subject:
        user.oidc_subject = subject
    if not user.is_active:
        db.commit()
        return RedirectResponse("/?login_error=disabled", status_code=302)
    _start_session(request, db, user)
    return RedirectResponse("/", status_code=302)
