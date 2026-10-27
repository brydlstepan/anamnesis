"""Admin API — separate, non-patient account; never exposes medical data (SPEC §9.6)."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import SUPPORTED_LANGUAGES, Settings
from ..db import get_db
from ..deps import (
    SESSION_ADMIN,
    all_app_settings,
    audit,
    client_ip,
    current_admin,
    get_settings,
)
from ..ids import iso, utcnow
from ..models import AdminAccount, AppSetting, AuditEvent, User
from ..security import hash_password, password_problem, verify_password
from ..users import create_user, delete_user_and_data, normalize_email

log = logging.getLogger("anamnesis.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


def seed_admin(db: Session, settings: Settings) -> None:
    """Create/update the admin account from env on every start (Q21)."""
    if not settings.admin_password:
        log.warning("ANAMNESIS_ADMIN_PASSWORD not set — admin login disabled")
        return
    if problem := password_problem(settings.admin_password):
        raise RuntimeError(f"ANAMNESIS_ADMIN_PASSWORD rejected: {problem}")
    admin = db.scalar(select(AdminAccount).where(AdminAccount.username == settings.admin_username))
    if admin is None:
        db.add(AdminAccount(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
        log.info("Admin account '%s' created", settings.admin_username)
    elif not verify_password(admin.password_hash, settings.admin_password):
        admin.password_hash = hash_password(settings.admin_password)
        admin.updated_at = utcnow()
        log.info("Admin password for '%s' updated from environment", settings.admin_username)
    # Remove admin accounts whose username is no longer configured.
    for stale in db.scalars(select(AdminAccount).where(AdminAccount.username != settings.admin_username)):
        db.delete(stale)
    db.commit()


# ---------------------------------------------------------------- auth


class AdminLogin(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=1024)


@router.post("/auth/login")
def admin_login(body: AdminLogin, request: Request, db: Session = Depends(get_db)) -> dict:
    limiter = request.app.state.rate_limiter
    key = f"admin:{client_ip(request)}"
    if not limiter.allowed(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, try again later")
    admin = db.scalar(select(AdminAccount).where(AdminAccount.username == body.username))
    if not verify_password(admin.password_hash if admin else None, body.password) or admin is None:
        limiter.fail(key)
        audit(db, request, action="admin.login_failed", target=body.username[:100])
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    limiter.reset(key)
    request.session.clear()
    request.session[SESSION_ADMIN] = admin.id
    admin.last_login_at = utcnow()
    audit(db, request, action="admin.login", actor=admin)
    db.commit()
    return {"username": admin.username}


@router.post("/auth/logout", status_code=204)
def admin_logout(request: Request) -> None:
    request.session.pop(SESSION_ADMIN, None)


@router.get("/auth/me")
def admin_me(admin: AdminAccount = Depends(current_admin)) -> dict:
    return {"username": admin.username}


# ---------------------------------------------------------------- users


def admin_user_out(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "auth_provider": u.auth_provider,
        "is_active": u.is_active,
        "created_at": iso(u.created_at),
        "last_login_at": iso(u.last_login_at),
    }


@router.get("/users")
def list_users(
    q: str = Query("", max_length=100), _: AdminAccount = Depends(current_admin), db: Session = Depends(get_db)
) -> list[dict]:
    stmt = select(User)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(User.email.like(like), User.display_name.ilike(like)))
    return [admin_user_out(u) for u in db.scalars(stmt.order_by(User.email))]


class UserCreate(BaseModel):
    email: str = Field(max_length=320)
    display_name: str = Field("", max_length=200)
    password: str = Field(max_length=1024)


@router.post("/users", status_code=201)
def create_local_user(
    body: UserCreate, request: Request, admin: AdminAccount = Depends(current_admin), db: Session = Depends(get_db)
) -> dict:
    try:
        email = normalize_email(body.email)
    except ValueError as e:
        raise HTTPException(422, "Invalid email") from e
    if problem := password_problem(body.password):
        raise HTTPException(422, problem)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "A user with this email already exists")
    user = create_user(
        db, email=email, provider="local", display_name=body.display_name, password_hash=hash_password(body.password)
    )
    audit(db, request, action="user.create", actor=admin, target=email)
    db.commit()
    return admin_user_out(user)


class UserUpdate(BaseModel):
    is_active: bool | None = None
    display_name: str | None = Field(None, max_length=200)
    password: str | None = Field(None, max_length=1024)


@router.patch("/users/{user_id}")
def update_user(
    user_id: str, body: UserUpdate, request: Request,
    admin: AdminAccount = Depends(current_admin), db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if body.is_active is not None:
        user.is_active = body.is_active
        audit(db, request, action="user.enable" if body.is_active else "user.disable", actor=admin, target=user.email)
    if body.display_name:
        user.display_name = body.display_name.strip()
    if body.password is not None:
        if user.auth_provider != "local":
            raise HTTPException(400, "Password of OIDC users is managed by the identity provider")
        if problem := password_problem(body.password):
            raise HTTPException(422, problem)
        user.password_hash = hash_password(body.password)
        audit(db, request, action="user.password_reset", actor=admin, target=user.email)
    db.commit()
    return admin_user_out(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str, request: Request,
    confirm_email: str = Query(..., description="Must equal the user's email"),
    admin: AdminAccount = Depends(current_admin), db: Session = Depends(get_db),
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if confirm_email.strip().lower() != user.email:
        raise HTTPException(422, "confirm_email does not match")
    email = user.email
    delete_user_and_data(db, user, get_settings(request).files_dir)
    audit(db, request, action="user.delete", actor=admin, target=email)
    db.commit()


# ---------------------------------------------------------------- settings & audit


class SettingsUpdate(BaseModel):
    user_directory_enabled: bool | None = None
    max_upload_mb: int | None = Field(None, ge=1, le=2048)
    default_language: Literal["cs", "en"] | None = None
    access_log_retention_days: int | None = Field(None, ge=30, le=3650)


@router.get("/settings")
def get_settings_(request: Request, _: AdminAccount = Depends(current_admin), db: Session = Depends(get_db)) -> dict:
    s = all_app_settings(db)
    s["default_language"] = s["default_language"] or get_settings(request).default_language
    return {**s, "languages": list(SUPPORTED_LANGUAGES)}


@router.put("/settings")
def put_settings(
    body: SettingsUpdate, request: Request,
    admin: AdminAccount = Depends(current_admin), db: Session = Depends(get_db),
) -> dict:
    for key, value in body.model_dump(exclude_none=True).items():
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
        audit(db, request, action="settings.update", actor=admin, target=f"{key}={value}")
    db.commit()
    return get_settings_(request, admin, db)


@router.get("/audit")
def admin_audit(
    limit: int = Query(200, le=1000), _: AdminAccount = Depends(current_admin), db: Session = Depends(get_db)
) -> list[dict]:
    """Account-level events only — no per-person medical access events."""
    rows = db.scalars(
        select(AuditEvent).where(AuditEvent.person_id.is_(None)).order_by(AuditEvent.ts.desc()).limit(limit)
    )
    return [
        {"ts": iso(e.ts), "actor_kind": e.actor_kind, "actor": e.actor_label, "action": e.action,
         "target": e.target, "ip": e.ip}
        for e in rows
    ]
