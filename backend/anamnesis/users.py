"""User lifecycle helpers shared by OIDC provisioning, admin and local login."""

import shutil
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .ids import utcnow
from .models import Person, Share, User


def normalize_email(email: str) -> str:
    email = (email or "").strip().lower()
    if "@" not in email or len(email) > 320 or email.startswith("@") or email.endswith("@"):
        raise ValueError("invalid email")
    return email


def create_user(
    db: Session,
    *,
    email: str,
    provider: str,
    display_name: str = "",
    password_hash: str | None = None,
    oidc_subject: str | None = None,
) -> User:
    """Creates User + its Person (1:1 in v1) and activates pending shares. Caller commits."""
    email = normalize_email(email)
    user = User(
        email=email,
        display_name=display_name.strip() or email.split("@")[0],
        auth_provider=provider,
        password_hash=password_hash,
        oidc_subject=oidc_subject,
    )
    db.add(user)
    db.flush()
    db.add(Person(user_id=user.id, name=user.display_name))
    activate_pending_shares(db, user)
    return user


def activate_pending_shares(db: Session, user: User) -> None:
    db.execute(
        update(Share)
        .where(Share.grantee_email == user.email, Share.grantee_user_id.is_(None))
        .values(grantee_user_id=user.id, activated_at=utcnow())
    )


def own_person(db: Session, user: User) -> Person | None:
    return db.scalar(select(Person).where(Person.user_id == user.id))


def delete_user_and_data(db: Session, user: User, files_dir: Path) -> None:
    """Deletes the user, their Person, records, attachments and files on disk. Caller commits."""
    person = own_person(db, user)
    if person is not None:
        person_dir = files_dir / person.id
        db.delete(person)
        db.flush()
        if person_dir.is_dir():
            shutil.rmtree(person_dir, ignore_errors=True)
    db.delete(user)
