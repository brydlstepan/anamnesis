"""Records CRUD (native records editable; imported records read-only — Q13), schema and regions."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import audit, audit_view, current_user, get_settings, load_person
from ..ids import iso, utcnow
from ..models import Attachment, Record, RecordVersion, User
from ..record_types import RECORD_TYPES, RecordValidationError, schema_json, validate_record
from ..regions import all_regions, descendants, region_base_id, regions_by_id
from ..storage import delete_attachment

router = APIRouter(prefix="/api/v1", tags=["records"])

COLUMN_FIELDS = ("title", "date", "end_date", "status")


def attachment_out(a: Attachment) -> dict[str, Any]:
    return {
        "id": a.id,
        "filename": a.filename,
        "mime": a.mime,
        "size": a.size,
        "record_id": a.record_id,
        "created_at": iso(a.created_at),
        "url": f"/api/v1/attachments/{a.id}/content",
    }


def record_out(r: Record, role: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": r.id,
        "person_id": r.person_id,
        "type": r.type,
        "title": r.title,
        "date": r.date,
        "end_date": r.end_date,
        "status": r.status,
        "regions": r.regions or [],
        **(r.data or {}),
        "attachments": [attachment_out(a) for a in r.attachments],
        "review_state": r.review_state,
        "origin": r.origin,
        "version": r.version,
        "created_at": iso(r.created_at),
        "updated_at": iso(r.updated_at),
    }
    if role is not None:
        out["editable"] = role in ("owner", "editor") and r.origin == "native"
    return out


def _snapshot(db: Session, r: Record, user: User) -> None:
    db.flush()
    db.refresh(r, ["attachments"])
    db.add(RecordVersion(record_id=r.id, version=r.version, snapshot=record_out(r), actor_user_id=user.id))


def _apply(r: Record, cleaned: dict[str, Any]) -> None:
    for k in COLUMN_FIELDS:
        setattr(r, k, cleaned.pop(k, None))
    r.regions = cleaned.pop("regions", [])
    r.data = cleaned


def _validate_links(db: Session, person_id: str, cleaned: dict[str, Any], self_id: str | None = None) -> None:
    ids = set(cleaned.get("links", [])) | set(cleaned.get("reason", []))
    if not ids:
        return
    if self_id in ids:
        raise HTTPException(422, [{"field": "links", "message": "a record cannot link to itself"}])
    found = set(db.scalars(
        select(Record.id).where(Record.person_id == person_id, Record.id.in_(ids), Record.deleted_at.is_(None))
    ))
    if missing := ids - found:
        raise HTTPException(422, [{"field": "links", "message": f"unknown record ids: {', '.join(sorted(missing))}"}])


def _resolve_attachments(db: Session, person_id: str, ids: Any, record_id: str | None) -> list[Attachment]:
    if ids is None:
        return []
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise HTTPException(422, [{"field": "attachment_ids", "message": "must be a list of ids"}])
    atts = list(db.scalars(select(Attachment).where(Attachment.id.in_(ids), Attachment.person_id == person_id)))
    if len(atts) != len(set(ids)) or any(a.record_id not in (None, record_id) for a in atts):
        raise HTTPException(422, [{"field": "attachment_ids", "message": "unknown or foreign attachment"}])
    return atts


@router.get("/schema")
def schema() -> dict:
    return {"types": schema_json()}


@router.get("/regions")
def regions() -> list[dict]:
    return all_regions()


@router.get("/persons/{person_id}/records")
def list_records(
    person_id: str,
    request: Request,
    type: str | None = Query(None),
    q: str | None = Query(None, max_length=200),
    region: str | None = Query(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    person, role = load_person(db, user, person_id)
    audit_view(db, request, user, person)
    stmt = select(Record).where(Record.person_id == person.id, Record.deleted_at.is_(None))
    if type:
        if type not in RECORD_TYPES:
            raise HTTPException(422, "unknown type")
        stmt = stmt.where(Record.type == type)
    if q and q.strip():
        stmt = stmt.where(Record.title.ilike(f"%{q.strip()}%"))
    rows = list(db.scalars(stmt.order_by(Record.date.desc(), Record.created_at.desc())))
    if region:
        if region not in regions_by_id():
            raise HTTPException(422, "unknown region")
        wanted = descendants(region)
        rows = [r for r in rows if any(region_base_id(x) in wanted for x in (r.regions or []))]
    return [record_out(r, role) for r in rows]


@router.post("/persons/{person_id}/records", status_code=201)
def create_record(
    person_id: str,
    request: Request,
    payload: dict[str, Any] = Body(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    person, role = load_person(db, user, person_id, "editor")
    atts = _resolve_attachments(db, person.id, payload.get("attachment_ids"), None)
    try:
        cleaned = validate_record(payload.get("type"), payload, has_attachments=bool(atts))
    except RecordValidationError as e:
        raise HTTPException(422, e.errors) from e
    _validate_links(db, person.id, cleaned)
    r = Record(person_id=person.id, type=payload["type"], created_by_user_id=user.id, updated_by_user_id=user.id)
    _apply(r, cleaned)
    db.add(r)
    db.flush()
    for a in atts:
        a.record_id = r.id
    _snapshot(db, r, user)
    audit(db, request, action="record.create", actor=user, person_id=person.id, target=r.id)
    db.commit()
    return record_out(r, role)


def _load_record(db: Session, user: User, record_id: str, min_role: str = "viewer") -> tuple[Record, str]:
    r = db.get(Record, record_id)
    if r is None or r.deleted_at is not None:
        raise HTTPException(404, "Record not found")
    _, role = load_person(db, user, r.person_id, min_role)
    return r, role


@router.get("/records/{record_id}")
def get_record(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    r, role = _load_record(db, user, record_id)
    return record_out(r, role)


@router.put("/records/{record_id}")
def update_record(
    record_id: str,
    request: Request,
    payload: dict[str, Any] = Body(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    r, role = _load_record(db, user, record_id, "editor")
    if r.origin != "native":
        raise HTTPException(409, "Imported records are read-only; edit them in their source")
    if payload.get("type", r.type) != r.type:
        raise HTTPException(422, [{"field": "type", "message": "type cannot be changed"}])
    ids = payload.get("attachment_ids")
    atts = _resolve_attachments(db, r.person_id, ids, r.id) if ids is not None else list(r.attachments)
    try:
        cleaned = validate_record(r.type, payload, has_attachments=bool(atts))
    except RecordValidationError as e:
        raise HTTPException(422, e.errors) from e
    _validate_links(db, r.person_id, cleaned, r.id)
    if ids is not None:  # attachment_ids is the full desired set
        keep = {a.id for a in atts}
        for a in list(r.attachments):
            if a.id not in keep:
                delete_attachment(db, get_settings(request).files_dir, a)
        for a in atts:
            a.record_id = r.id
    _apply(r, cleaned)
    r.version += 1
    r.updated_at = utcnow()
    r.updated_by_user_id = user.id
    _snapshot(db, r, user)
    audit(db, request, action="record.update", actor=user, person_id=r.person_id, target=r.id)
    db.commit()
    return record_out(r, role)


@router.delete("/records/{record_id}", status_code=204)
def delete_record(
    record_id: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    r, _ = _load_record(db, user, record_id, "editor")
    if r.origin != "native":
        raise HTTPException(409, "Imported records are read-only; delete them in their source")
    r.deleted_at = utcnow()  # soft delete; history kept
    r.updated_by_user_id = user.id
    audit(db, request, action="record.delete", actor=user, person_id=r.person_id, target=r.id)
    db.commit()


@router.get("/records/{record_id}/versions")
def record_versions(record_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list:
    r, _ = _load_record(db, user, record_id)
    rows = db.scalars(
        select(RecordVersion).where(RecordVersion.record_id == r.id).order_by(RecordVersion.version.desc())
    )
    return [{"version": v.version, "created_at": iso(v.created_at), "snapshot": v.snapshot} for v in rows]
