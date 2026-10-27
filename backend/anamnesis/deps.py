"""Request dependencies: current user/admin, person access, settings, audit."""

from datetime import timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .db import get_db
from .ids import utcnow
from .models import AdminAccount, AppSetting, AuditEvent, Person, Share, User

ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}
SESSION_USER = "uid"
SESSION_ADMIN = "aid"

DEFAULT_APP_SETTINGS: dict[str, Any] = {
    "user_directory_enabled": False,  # Q41
    "max_upload_mb": 50,
    "default_language": None,  # None -> env default
    "access_log_retention_days": 365,
}


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get(SESSION_USER)
    user = db.get(User, uid) if uid else None
    if user is None or not user.is_active:
        request.session.pop(SESSION_USER, None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


def current_admin(request: Request, db: Session = Depends(get_db)) -> AdminAccount:
    aid = request.session.get(SESSION_ADMIN)
    admin = db.get(AdminAccount, aid) if aid else None
    if admin is None:
        request.session.pop(SESSION_ADMIN, None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return admin


def role_for(db: Session, user: User, person: Person) -> str | None:
    if person.user_id == user.id:
        return "owner"
    share = db.scalar(
        select(Share).where(Share.person_id == person.id, Share.grantee_user_id == user.id)
    )
    return share.role if share else None


def load_person(db: Session, user: User, person_id: str, min_role: str = "viewer") -> tuple[Person, str]:
    """Returns (person, role). 404 when no access at all (no enumeration), 403 when role too low."""
    person = db.get(Person, person_id)
    role = role_for(db, user, person) if person else None
    if person is None or role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires {min_role} role")
    return person, role


def get_app_setting(db: Session, key: str) -> Any:
    row = db.get(AppSetting, key)
    return row.value if row is not None else DEFAULT_APP_SETTINGS[key]


def all_app_settings(db: Session) -> dict[str, Any]:
    return {k: get_app_setting(db, k) for k in DEFAULT_APP_SETTINGS}


def audit(
    db: Session,
    request: Request | None,
    *,
    action: str,
    actor: User | AdminAccount | None = None,
    person_id: str | None = None,
    target: str | None = None,
    detail: str | None = None,
) -> None:
    """Adds an audit event to the session (caller commits)."""
    if isinstance(actor, User):
        kind, aid, label = "user", actor.id, actor.email
    elif isinstance(actor, AdminAccount):
        kind, aid, label = "admin", actor.id, actor.username
    else:
        kind, aid, label = "system", None, "system"
    db.add(
        AuditEvent(
            actor_kind=kind,
            actor_id=aid,
            actor_label=label,
            person_id=person_id,
            action=action,
            target=target,
            detail=detail,
            ip=client_ip(request) if request else None,
        )
    )


def audit_view(db: Session, request: Request, user: User, person: Person) -> None:
    """Log that someone other than the owner viewed a profile, at most every 10 minutes per viewer."""
    if person.user_id == user.id:
        return
    since = utcnow() - timedelta(minutes=10)
    recent = db.scalar(
        select(AuditEvent.id).where(
            AuditEvent.person_id == person.id,
            AuditEvent.actor_id == user.id,
            AuditEvent.action == "person.view",
            AuditEvent.ts >= since,
        )
    )
    if recent is None:
        audit(db, request, action="person.view", actor=user, person_id=person.id)
        db.commit()
