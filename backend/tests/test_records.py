import io

import pytest

from anamnesis.models import Record
from anamnesis.record_types import RecordValidationError, validate_record
from anamnesis.regions import all_regions, normalize_region

PDF = b"%PDF-1.4\n%test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


# ------------------------------------------------------------ pure validation


def test_regions_vocabulary_consistent():
    ids = [r["id"] for r in all_regions()]
    assert len(ids) == len(set(ids))
    assert "systemic" in ids and "knee" in ids
    parents = {r["parent"] for r in all_regions()} - {None}
    assert parents <= set(ids)


@pytest.mark.parametrize(
    "ref,expected",
    [("knee:left", "knee:left"), ("liver", "liver"), ({"region": "eye:both"}, "eye:both"),
     ({"region": "knee:right", "offset": [0.1, -0.2, 1]}, {"region": "knee:right", "offset": [0.1, -0.2, 1.0]})],
)
def test_normalize_region_ok(ref, expected):
    assert normalize_region(ref) == expected


@pytest.mark.parametrize("ref", ["knee", "liver:left", "kne:left", "knee:up", {"region": "liver", "offset": [2, 0, 0]}])
def test_normalize_region_errors(ref):
    with pytest.raises(ValueError):
        normalize_region(ref)


def test_validate_required_and_extra():
    with pytest.raises(RecordValidationError) as e:
        validate_record("observation", {"title": "Chol", "date": "2025-13-01", "name": "x"}, has_attachments=False)
    fields = {err["field"] for err in e.value.errors}
    assert fields == {"date", "value", "unit"}
    ok = validate_record(
        "observation",
        {"title": "Chol", "date": "2025-11-04", "name": "Total cholesterol", "value": 5.4, "unit": "mmol/L",
         "reference_range": {"low": 2.9, "high": 5.0}, "future_field": 1},
        has_attachments=False,
    )
    assert ok["value"] == 5.4 and ok["extra"] == {"future_field": 1}
    with pytest.raises(RecordValidationError):
        validate_record("nope", {}, has_attachments=False)
    with pytest.raises(RecordValidationError):
        validate_record("document", {"title": "Report", "date": "2021"}, has_attachments=False)


# ------------------------------------------------------------ API


def test_record_crud_and_versions(make_user):
    alice = make_user("alice@example.com")
    pid = alice.me["person_id"]
    base = f"/api/v1/persons/{pid}/records"

    r = alice.post(base, json={"type": "procedure", "title": "Meniscus repair", "date": "2021-03-18"})
    assert r.status_code == 422 and r.json()["detail"][0]["field"] == "regions"

    cond = alice.post(base, json={"type": "condition", "title": "Meniscus tear", "date": "2021-02",
                                  "status": "resolved", "regions": ["knee:left"]}).json()
    proc = alice.post(base, json={"type": "procedure", "title": "Meniscus repair", "date": "2021-03-18",
                                  "regions": ["knee:left"], "links": [cond["id"]], "facility": "Bulovka",
                                  "codes": [{"system": "icd10", "code": "S83.2"}]})
    assert proc.status_code == 201, proc.text
    proc = proc.json()
    assert proc["editable"] is True and proc["origin"] == "native" and proc["version"] == 1
    assert proc["facility"] == "Bulovka"

    # unknown link
    bad = alice.post(base, json={"type": "condition", "title": "x", "date": "2020", "status": "active",
                                 "links": ["does-not-exist"]})
    assert bad.status_code == 422

    # update
    upd = alice.put(f"/api/v1/records/{proc['id']}", json={**proc, "title": "Arthroscopic meniscus repair"})
    assert upd.status_code == 200 and upd.json()["version"] == 2
    assert alice.put(f"/api/v1/records/{proc['id']}", json={**proc, "type": "exam"}).status_code == 422
    versions = alice.get(f"/api/v1/records/{proc['id']}/versions").json()
    assert [v["version"] for v in versions] == [2, 1]

    # filters
    assert len(alice.get(base).json()) == 2
    assert len(alice.get(base, params={"type": "procedure"}).json()) == 1
    assert len(alice.get(base, params={"region": "lower_limb"}).json()) == 2
    assert len(alice.get(base, params={"region": "head_neck"}).json()) == 0
    assert len(alice.get(base, params={"q": "arthro"}).json()) == 1

    # delete (soft)
    assert alice.delete(f"/api/v1/records/{proc['id']}").status_code == 204
    assert alice.get(f"/api/v1/records/{proc['id']}").status_code == 404
    assert len(alice.get(base).json()) == 1


def test_imported_records_are_read_only(make_user, app):
    alice = make_user("alice@example.com")
    pid = alice.me["person_id"]
    with app.state.sessionmaker() as db:
        rec = Record(person_id=pid, type="exam", title="MRI knee", date="2021-02-02", data={"kind": "imaging"},
                     origin="source:outline-1", source_id="outline-1", external_id="doc-123")
        db.add(rec)
        db.commit()
        rid = rec.id
    got = alice.get(f"/api/v1/records/{rid}").json()
    assert got["editable"] is False
    assert alice.put(f"/api/v1/records/{rid}", json={**got, "title": "x"}).status_code == 409
    assert alice.delete(f"/api/v1/records/{rid}").status_code == 409


def test_attachments_flow(make_user, settings):
    alice = make_user("alice@example.com")
    bob = make_user("bob@example.com")
    pid = alice.me["person_id"]

    up = alice.post(f"/api/v1/persons/{pid}/attachments", files={"file": ("report.pdf", io.BytesIO(PDF), "text/plain")})
    assert up.status_code == 201, up.text
    att = up.json()
    assert att["mime"] == "application/pdf"  # sniffed, client type ignored
    stored = settings.files_dir / pid
    assert stored.is_dir()

    # disallowed type
    evil = alice.post(f"/api/v1/persons/{pid}/attachments",
                      files={"file": ("x.html", io.BytesIO(b"<script>alert(1)</script>"), "text/html")})
    assert evil.status_code == 422

    # document requires attachment
    doc = {"type": "document", "title": "Discharge summary", "date": "2021-03-20"}
    assert alice.post(f"/api/v1/persons/{pid}/records", json=doc).status_code == 422
    rec = alice.post(f"/api/v1/persons/{pid}/records", json={**doc, "attachment_ids": [att["id"]]})
    assert rec.status_code == 201, rec.text
    rec = rec.json()
    assert rec["attachments"][0]["id"] == att["id"]

    # download
    dl = alice.get(att["url"])
    assert dl.status_code == 200 and dl.content == PDF
    assert "sandbox" in dl.headers["content-security-policy"]
    assert bob.get(att["url"]).status_code == 404

    # bob cannot attach alice's file to his own record
    bpid = bob.me["person_id"]
    stolen = bob.post(f"/api/v1/persons/{bpid}/records", json={**doc, "attachment_ids": [att["id"]]})
    assert stolen.status_code == 422

    # replace attachment set on update -> old file removed
    up2 = alice.post(f"/api/v1/persons/{pid}/attachments", files={"file": ("photo.png", io.BytesIO(PNG), "image/png")})
    att2 = up2.json()
    upd = alice.put(f"/api/v1/records/{rec['id']}", json={**rec, "attachment_ids": [att2["id"]]})
    assert upd.status_code == 200
    assert [a["id"] for a in upd.json()["attachments"]] == [att2["id"]]
    assert alice.get(att["url"]).status_code == 404


def test_upload_size_limit(make_user, admin_client):
    admin_client.put("/api/admin/settings", json={"max_upload_mb": 1})
    alice = make_user("alice@example.com")
    pid = alice.me["person_id"]
    big = PDF + b"0" * (1024 * 1024 + 10)
    r = alice.post(f"/api/v1/persons/{pid}/attachments", files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")})
    assert r.status_code == 422


def test_schema_endpoint(make_user):
    alice = make_user("alice@example.com")
    types = {t["type"]: t for t in alice.get("/api/v1/schema").json()["types"]}
    assert set(types) == {"condition", "procedure", "exam", "observation", "medication", "allergy",
                          "vaccination", "document"}
    proc = {f["name"]: f for f in types["procedure"]["fields"]}
    assert proc["regions"]["required"] is True and proc["title"]["required"] is True
    assert len(alice.get("/api/v1/regions").json()) > 50
