"""Database models. See SPEC.md §3–4.

User and Person are separate tables linked 1:1 in v1 so that dependent profiles
(Person without a User) can be added later without a migration (Q19).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .ids import utcnow, uuid7


def _id() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=uuid7)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = _id()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    auth_provider: Mapped[str] = mapped_column(String(16))  # local | oidc
    password_hash: Mapped[str | None] = mapped_column(String(255))
    oidc_subject: Mapped[str | None] = mapped_column(String(255), index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    language: Mapped[str | None] = mapped_column(String(8))
    show_access_log: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = _created()
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    person: Mapped["Person | None"] = relationship(back_populates="user", uselist=False)


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[str] = _id()
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(200))
    birth_date: Mapped[str | None] = mapped_column(String(10))
    sex: Mapped[str | None] = mapped_column(String(16))
    body_model: Mapped[str] = mapped_column(String(8), default="male")  # independent of sex (Q35)
    blood_type: Mapped[str | None] = mapped_column(String(8))
    emergency_contacts: Mapped[list[Any]] = mapped_column(JSON, default=list)
    organ_donation: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User | None] = relationship(back_populates="person")


class Share(Base):
    """Owner grants another user (by email) viewer/editor access. Pending until that email exists."""

    __tablename__ = "shares"
    __table_args__ = (UniqueConstraint("person_id", "grantee_email"),)

    id: Mapped[str] = _id()
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    grantee_email: Mapped[str] = mapped_column(String(320), index=True)
    grantee_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    role: Mapped[str] = mapped_column(String(8))  # viewer | editor
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created()
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Record(Base):
    __tablename__ = "records"
    __table_args__ = (
        Index("ix_records_person_date", "person_id", "date"),
        UniqueConstraint("source_id", "external_id"),
    )

    id: Mapped[str] = _id()
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(300))
    date: Mapped[str] = mapped_column(String(25))  # ISO, partial allowed
    end_date: Mapped[str | None] = mapped_column(String(25))
    status: Mapped[str | None] = mapped_column(String(16))
    regions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # all other fields
    review_state: Mapped[str] = mapped_column(String(12), default="confirmed")  # confirmed | draft
    origin: Mapped[str] = mapped_column(String(64), default="native")  # native | source:<id>
    source_id: Mapped[str | None] = mapped_column(String(36))
    external_id: Mapped[str | None] = mapped_column(String(512))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attachments: Mapped[list["Attachment"]] = relationship(back_populates="record")


class RecordVersion(Base):
    __tablename__ = "record_versions"
    __table_args__ = (UniqueConstraint("record_id", "version"),)

    id: Mapped[str] = _id()
    record_id: Mapped[str] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created()


class Attachment(Base):
    """File stored at <data>/files/<person_id>/<sha[:2]>/<sha> (Q28)."""

    __tablename__ = "attachments"

    id: Mapped[str] = _id()
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[str | None] = mapped_column(
        ForeignKey("records.id", ondelete="SET NULL"), index=True, nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created()

    record: Mapped[Record | None] = relationship(back_populates="attachments")


class AdminAccount(Base):
    """Separate, non-patient admin seeded from .env (Q21)."""

    __tablename__ = "admin_accounts"

    id: Mapped[str] = _id()
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """Per-person access log (owner-visible) and account-level events (admin-visible)."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_person_ts", "person_id", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_kind: Mapped[str] = mapped_column(String(8))  # user | admin | system
    actor_id: Mapped[str | None] = mapped_column(String(36))
    actor_label: Mapped[str] = mapped_column(String(320), default="")
    person_id: Mapped[str | None] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str | None] = mapped_column(String(200))
    via: Mapped[str] = mapped_column(String(8), default="ui")  # ui | api | mcp
    ip: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
