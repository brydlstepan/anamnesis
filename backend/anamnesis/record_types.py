"""Record types, their required/optional fields and validation (SPEC §4.2, docs/medrecord-schema.md).

The same definitions drive the in-app form (via GET /api/v1/schema) and API validation,
so a field added here shows up in the UI automatically.
"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .regions import normalize_region

DATE_RE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01])(T([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?)?)?)?$")
CODE_SYSTEMS = ("icd10", "snomed", "loinc", "atc", "custom")
MAX_TEXT = 2_000
MAX_LONG_TEXT = 50_000


@dataclass(frozen=True)
class FieldDef:
    name: str
    kind: str  # text|textarea|date|enum|number|text_or_number|regions|codes|tags|links|list|range|attachments
    required: bool = False
    options: tuple[str, ...] = field(default_factory=tuple)


def _f(name: str, kind: str = "text", required: bool = False, options: tuple[str, ...] = ()) -> FieldDef:
    return FieldDef(name, kind, required, options)


# Fields every type has. title + date are always required.
COMMON_HEAD = [_f("title", required=True), _f("date", "date", required=True)]
COMMON_TAIL = [
    _f("end_date", "date"),
    _f("regions", "regions"),
    _f("description", "textarea"),
    _f("facility"),
    _f("practitioner"),
    _f("codes", "codes"),
    _f("tags", "tags"),
    _f("links", "links"),
]

TYPE_FIELDS: dict[str, list[FieldDef]] = {
    "condition": [
        _f("status", "enum", True, ("active", "resolved", "remission")),
        _f("severity", "enum", options=("mild", "moderate", "severe")),
    ],
    "procedure": [
        _f("regions", "regions", True),
        _f("outcome"),
        _f("implants", "list"),
    ],
    "exam": [
        _f("kind", "enum", True, ("imaging", "specialist", "preventive", "emergency", "other")),
        _f("findings", "textarea"),
    ],
    "observation": [
        _f("name", required=True),
        _f("value", "text_or_number", True),
        _f("unit", required=True),
        _f("reference_range", "range"),
        _f("interpretation", "enum", options=("low", "normal", "high", "critical")),
        _f("method"),
    ],
    "medication": [
        _f("name", required=True),
        _f("status", "enum", True, ("active", "stopped")),
        _f("dose"),
        _f("frequency"),
        _f("reason", "links"),
    ],
    "allergy": [
        _f("substance", required=True),
        _f("criticality", "enum", True, ("low", "high", "unknown")),
        _f("reaction"),
        _f("onset", "date"),
    ],
    "vaccination": [
        _f("vaccine", required=True),
        _f("dose_number", "number"),
        _f("batch"),
    ],
    "document": [
        _f("file", "attachments", True),
    ],
}
RECORD_TYPES = tuple(TYPE_FIELDS)

# Keys clients may send but that are handled outside of field validation.
RESERVED_KEYS = {
    "id", "person_id", "type", "review_state", "origin", "provenance", "attachments", "attachment_ids",
    "created_at", "updated_at", "version", "editable", "deleted_at", "schema", "extra",
}


def fields_for(type_: str) -> list[FieldDef]:
    """Ordered field list for a type; type-specific definitions override common ones (e.g. regions)."""
    specific = TYPE_FIELDS[type_]
    names = {f.name for f in specific}
    return COMMON_HEAD + specific + [f for f in COMMON_TAIL if f.name not in names]


def schema_json() -> list[dict[str, Any]]:
    out = []
    for t in RECORD_TYPES:
        out.append({"type": t, "fields": [{**asdict(f), "options": list(f.options)} for f in fields_for(t)]})
    return out


class RecordValidationError(Exception):
    def __init__(self, errors: list[dict[str, str]]):
        super().__init__("invalid record")
        self.errors = errors


def _is_num(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def _empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list | dict) and not v)


def _clean_value(f: FieldDef, v: Any) -> Any:
    """Returns cleaned value or raises ValueError."""
    k = f.kind
    if k in ("text", "textarea"):
        if not isinstance(v, str):
            raise ValueError("must be text")
        v = v.strip()
        limit = MAX_LONG_TEXT if k == "textarea" else MAX_TEXT
        if len(v) > limit:
            raise ValueError(f"too long (max {limit} characters)")
        return v
    if k == "date":
        if not isinstance(v, str) or not DATE_RE.match(v.strip()):
            raise ValueError("must be an ISO date: YYYY, YYYY-MM, YYYY-MM-DD or YYYY-MM-DDTHH:MM")
        return v.strip()
    if k == "enum":
        if v not in f.options:
            raise ValueError(f"must be one of: {', '.join(f.options)}")
        return v
    if k == "number":
        if not _is_num(v):
            raise ValueError("must be a number")
        return v
    if k == "text_or_number":
        if _is_num(v):
            return v
        if isinstance(v, str) and v.strip() and len(v) <= MAX_TEXT:
            return v.strip()
        raise ValueError("must be a number or text")
    if k == "regions":
        if not isinstance(v, list):
            raise ValueError("must be a list of regions")
        out: list[Any] = []
        for item in v:
            norm = normalize_region(item)
            if norm not in out:
                out.append(norm)
        return out
    if k == "codes":
        if not isinstance(v, list):
            raise ValueError("must be a list of {system, code, display?}")
        out = []
        for c in v:
            if not isinstance(c, dict) or c.get("system") not in CODE_SYSTEMS or not isinstance(c.get("code"), str):
                raise ValueError(f"each code needs system ({', '.join(CODE_SYSTEMS)}) and code")
            item = {"system": c["system"], "code": c["code"].strip()}
            if isinstance(c.get("display"), str) and c["display"].strip():
                item["display"] = c["display"].strip()
            out.append(item)
        return out
    if k in ("tags", "links"):
        if isinstance(v, str):  # allow a single value
            v = [v]
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            raise ValueError("must be a list of strings")
        return list(dict.fromkeys(x.strip() for x in v))
    if k == "list":
        if not isinstance(v, list) or not all(isinstance(x, str | dict) for x in v):
            raise ValueError("must be a list")
        return v
    if k == "range":
        if not isinstance(v, dict):
            raise ValueError("must be {low?, high?, text?}")
        out_r: dict[str, Any] = {}
        for key in ("low", "high"):
            if v.get(key) is not None:
                if not _is_num(v[key]):
                    raise ValueError(f"{key} must be a number")
                out_r[key] = v[key]
        if isinstance(v.get("text"), str) and v["text"].strip():
            out_r["text"] = v["text"].strip()
        return out_r
    raise ValueError(f"unsupported field kind {k}")  # pragma: no cover


def validate_record(type_: Any, payload: dict[str, Any], *, has_attachments: bool) -> dict[str, Any]:
    """Validate a flat record payload. Returns cleaned dict of fields (unknown keys under 'extra')."""
    if type_ not in TYPE_FIELDS:
        raise RecordValidationError([{"field": "type", "message": f"must be one of: {', '.join(RECORD_TYPES)}"}])
    errors: list[dict[str, str]] = []
    cleaned: dict[str, Any] = {}
    defs = fields_for(type_)
    known = {f.name for f in defs}
    for f in defs:
        if f.kind == "attachments":
            if f.required and not has_attachments:
                errors.append({"field": f.name, "message": "at least one file is required"})
            continue
        v = payload.get(f.name)
        if _empty(v):
            if f.required:
                errors.append({"field": f.name, "message": "required"})
            continue
        try:
            cleaned[f.name] = _clean_value(f, v)
        except ValueError as e:
            errors.append({"field": f.name, "message": str(e)})
    extra = {k: v for k, v in payload.items() if k not in known and k not in RESERVED_KEYS}
    if extra:
        cleaned["extra"] = extra
    if errors:
        raise RecordValidationError(errors)
    return cleaned
