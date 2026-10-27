"""Persons (patient profiles), sharing and the optional user directory (SPEC §3.2)."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import audit, audit_view, current_user, get_app_setting, load_person
from ..ids import iso, utcnow
from ..models import AuditEvent, Person, Share, User
from ..record_types import DATE_RE
from ..users import normalize_email

router = APIRouter(prefix="/api/v1", tags=["persons"])

BLOOD_TYPES = ("0+", "0-", "A+", "A-", "B+", "B-", "AB+", "AB-")


def person_out(p: Person, role: str, me: User) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "role": role,
        "is_me": p.user_id == me.id,
        "birth_date": p.birth_date,
        "sex": p.sex,
        "body_model": p.body_model,
        "blood_type": p.blood_type,
        "emergency_contacts": p.emergency_contacts or [],
        "organ_donation": p.organ_donation,
        "updated_at": iso(p.updated_at),
    }


@router.get("/persons")
def list_persons(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    out = []
    own = db.scalar(select(Person).where(Person.user_id == user.id))
    if own:
        out.append(person_out(own, "owner", user))
    rows = db.execute(
        select(Person, Share.role)
        .join(Share, Share.person_id == Person.id)
        .where(Share.grantee_user_id == user.id)
        .order_by(Person.name)
    ).all()
    out.extend(person_out(p, role, user) for p, role in rows)
    return out


@router.get("/persons/{person_id}")
def get_person(
    person_id: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    person, role = load_person(db, user, person_id)
    audit_view(db, request, user, person)
    return person_out(person, role, user)


class EmergencyContact(BaseModel):
    name: str = Field(max_length=200)
    phone: str = Field("", max_length=50)
    relation: str = Field("", max_length=100)


class PersonUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    birth_date: str | None = None
    sex: Literal["male", "female", "other", "unknown"] | None = None
    body_model: Literal["male", "female"] | None = None
    blood_type: str | None = None
    emergency_contacts: list[EmergencyContact] | None = None
    organ_donation: str | None = Field(None, max_length=500)


@router.patch("/persons/{person_id}")
def update_person(
    person_id: str,
    body: PersonUpdate,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    person, role = load_person(db, user, person_id, "editor")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and not (data["name"] or "").strip():
        raise HTTPException(422, "name must not be empty")
    if data.get("birth_date") and not DATE_RE.match(data["birth_date"]):
        raise HTTPException(422, "birth_date must be YYYY-MM-DD")
    if data.get("blood_type") and data["blood_type"] not in BLOOD_TYPES:
        raise HTTPException(422, f"blood_type must be one of {BLOOD_TYPES}")
    for k, v in data.items():
        if k == "body_model" and v is None:
            continue
        setattr(person, k, v.strip() if isinstance(v, str) else v)
    audit(db, request, action="person.update", actor=user, person_id=person.id)
    db.commit()
    return person_out(person, role, user)


# ---------------------------------------------------------------- sharing (owner only)


def share_out(s: Share, db: Session) -> dict[str, Any]:
    grantee = db.get(User, s.grantee_user_id) if s.grantee_user_id else None
    return {
        "id": s.id,
        "email": s.grantee_email,
        "display_name": grantee.display_name if grantee else None,
        "role": s.role,
        "status": "active" if s.grantee_user_id else "pending",
        "created_at": iso(s.created_at),
    }


@router.get("/persons/{person_id}/shares")
def list_shares(person_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list:
    person, _ = load_person(db, user, person_id, "owner")
    shares = db.scalars(select(Share).where(Share.person_id == person.id).order_by(Share.created_at))
    return [share_out(s, db) for s in shares]


class ShareIn(BaseModel):
    email: str = Field(max_length=320)
    role: Literal["viewer", "editor"]


@router.post("/persons/{person_id}/shares", status_code=201)
def create_share(
    person_id: str, body: ShareIn, request: Request,
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> dict:
    person, _ = load_person(db, user, person_id, "owner")
    try:
        email = normalize_email(body.email)
    except ValueError as e:
        raise HTTPException(422, "Invalid email") from e
    if email == user.email:
        raise HTTPException(422, "You cannot share your profile with yourself")
    exists = db.scalar(select(Share).where(Share.person_id == person.id, Share.grantee_email == email))
    if exists:
        raise HTTPException(409, "Already shared with this email")
    grantee = db.scalar(select(User).where(User.email == email))
    share = Share(
        person_id=person.id,
        grantee_email=email,
        grantee_user_id=grantee.id if grantee else None,
        activated_at=utcnow() if grantee else None,
        role=body.role,
        created_by_user_id=user.id,
    )
    db.add(share)
    audit(db, request, action="share.create", actor=user, person_id=person.id, target=f"{email}:{body.role}")
    db.commit()
    return share_out(share, db)


def _owned_share(db: Session, user: User, share_id: str) -> Share:
    share = db.get(Share, share_id)
    if share is None:
        raise HTTPException(404, "Share not found")
    load_person(db, user, share.person_id, "owner")
    return share


class ShareUpdate(BaseModel):
    role: Literal["viewer", "editor"]


@router.patch("/shares/{share_id}")
def update_share(
    share_id: str, body: ShareUpdate, request: Request,
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> dict:
    share = _owned_share(db, user, share_id)
    share.role = body.role
    audit(db, request, action="share.update", actor=user, person_id=share.person_id,
          target=f"{share.grantee_email}:{body.role}")
    db.commit()
    return share_out(share, db)


@router.delete("/shares/{share_id}", status_code=204)
def delete_share(
    share_id: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    share = _owned_share(db, user, share_id)
    audit(db, request, action="share.revoke", actor=user, person_id=share.person_id, target=share.grantee_email)
    db.delete(share)
    db.commit()


@router.get("/users/directory")
def user_directory(
    q: str = Query("", max_length=100), user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict]:
    """Only available when the admin enabled it (Q41)."""
    if not get_app_setting(db, "user_directory_enabled"):
        raise HTTPException(403, "User directory is disabled")
    stmt = select(User).where(User.is_active.is_(True), User.id != user.id)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(User.email.like(like), User.display_name.ilike(like)))
    return [{"email": u.email, "display_name": u.display_name} for u in db.scalars(stmt.order_by(User.email).limit(20))]


# ---------------------------------------------------------------- access log (owner only, Q42)


@router.get("/persons/{person_id}/access-log")
def access_log(
    person_id: str, limit: int = Query(200, le=1000),
    user: User = Depends(current_user), db: Session = Depends(get_db),
) -> list[dict]:
    person, _ = load_person(db, user, person_id, "owner")
    rows = db.scalars(
        select(AuditEvent).where(AuditEvent.person_id == person.id).order_by(AuditEvent.ts.desc()).limit(limit)
    )
    return [
        {"ts": iso(e.ts), "actor": e.actor_label, "action": e.action, "target": e.target, "via": e.via}
        for e in rows
    ]
