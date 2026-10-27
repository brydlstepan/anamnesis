"""Content-addressed, per-person file storage: <files>/<person_id>/<sha[:2]>/<sha> (Q28)."""

import hashlib
import os
import tempfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Attachment

CHUNK = 1024 * 1024

# Magic-byte sniffing — the client-supplied content type is never trusted.
ALLOWED_TYPES = {
    "application/pdf": "PDF",
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WebP",
    "image/heic": "HEIC",
    "model/gltf-binary": "GLB",
}
INLINE_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


class UploadRejected(Exception):
    pass


def sniff(head: bytes) -> str | None:
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:4] == b"glTF":
        return "model/gltf-binary"
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"heim", b"heis", b"mif1", b"msf1"):
        return "image/heic"
    return None


def safe_filename(name: str | None) -> str:
    name = os.path.basename((name or "file").replace("\\", "/")).strip()
    name = "".join(c for c in name if c.isprintable() and c not in '<>:"|?*')
    return (name or "file")[:255]


def path_for(files_dir: Path, person_id: str, sha: str) -> Path:
    return files_dir / person_id / sha[:2] / sha


async def store_upload(files_dir: Path, person_id: str, upload: UploadFile, max_bytes: int) -> tuple[str, str, int]:
    """Streams the upload to disk. Returns (sha256, mime, size). Raises UploadRejected."""
    person_dir = files_dir / person_id
    person_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    mime: str | None = None
    fd, tmp_name = tempfile.mkstemp(dir=person_dir, prefix=".upload-")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out:
            first = True
            while chunk := await upload.read(CHUNK):
                if first:
                    mime = sniff(chunk[:32])
                    if mime is None:
                        raise UploadRejected(f"Unsupported file type. Allowed: {', '.join(ALLOWED_TYPES.values())}")
                    first = False
                size += len(chunk)
                if size > max_bytes:
                    raise UploadRejected(f"File too large (max {max_bytes // (1024 * 1024)} MB)")
                h.update(chunk)
                out.write(chunk)
        if size == 0 or mime is None:
            raise UploadRejected("Empty file")
        sha = h.hexdigest()
        dest = path_for(files_dir, person_id, sha)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            tmp.unlink()
        else:
            tmp.replace(dest)
        return sha, mime, size
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def delete_attachment(db: Session, files_dir: Path, att: Attachment) -> None:
    """Deletes the row and the file if no other attachment of the same person references it."""
    others = db.scalar(
        select(func.count()).select_from(Attachment).where(
            Attachment.person_id == att.person_id, Attachment.sha256 == att.sha256, Attachment.id != att.id
        )
    )
    if not others:
        path_for(files_dir, att.person_id, att.sha256).unlink(missing_ok=True)
    db.delete(att)
