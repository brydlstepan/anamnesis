"""Attachment upload/download (SPEC §10.1). Files are uploaded first, then linked via attachment_ids."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import audit, current_user, get_app_setting, get_settings, load_person
from ..models import Attachment, Record, User
from ..storage import INLINE_TYPES, UploadRejected, delete_attachment, path_for, safe_filename, store_upload
from .records import attachment_out

router = APIRouter(prefix="/api/v1", tags=["attachments"])


@router.post("/persons/{person_id}/attachments", status_code=201)
async def upload_attachment(
    person_id: str,
    request: Request,
    file: UploadFile = File(...),
    record_id: str | None = Form(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    person, _ = load_person(db, user, person_id, "editor")
    if record_id:
        rec = db.get(Record, record_id)
        if rec is None or rec.person_id != person.id or rec.deleted_at is not None:
            raise HTTPException(404, "Record not found")
        if rec.origin != "native":
            raise HTTPException(409, "Imported records are read-only")
    max_bytes = int(get_app_setting(db, "max_upload_mb")) * 1024 * 1024
    try:
        sha, mime, size = await store_upload(get_settings(request).files_dir, person.id, file, max_bytes)
    except UploadRejected as e:
        raise HTTPException(422, str(e)) from e
    att = Attachment(
        person_id=person.id,
        record_id=record_id or None,
        filename=safe_filename(file.filename),
        mime=mime,
        size=size,
        sha256=sha,
        created_by_user_id=user.id,
    )
    db.add(att)
    audit(db, request, action="attachment.upload", actor=user, person_id=person.id, target=att.filename)
    db.commit()
    return attachment_out(att)


def _load(db: Session, user: User, attachment_id: str, min_role: str) -> Attachment:
    att = db.get(Attachment, attachment_id)
    if att is None:
        raise HTTPException(404, "Attachment not found")
    load_person(db, user, att.person_id, min_role)
    return att


@router.get("/attachments/{attachment_id}/content")
def download_attachment(
    attachment_id: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    att = _load(db, user, attachment_id, "viewer")
    path = path_for(get_settings(request).files_dir, att.person_id, att.sha256)
    if not path.is_file():
        raise HTTPException(410, "File missing on disk")
    disposition = "inline" if att.mime in INLINE_TYPES else "attachment"
    return FileResponse(
        path,
        media_type=att.mime,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(att.filename)}",
            "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
def remove_attachment(
    attachment_id: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    att = _load(db, user, attachment_id, "editor")
    if att.record is not None and att.record.origin != "native":
        raise HTTPException(409, "Imported records are read-only")
    audit(db, request, action="attachment.delete", actor=user, person_id=att.person_id, target=att.filename)
    delete_attachment(db, get_settings(request).files_dir, att)
    db.commit()
