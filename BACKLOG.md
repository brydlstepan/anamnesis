# Backlog (post-v1)

Items explicitly deferred during the design interview, plus ideas that came up. Not prioritized unless noted.

## Data sources
- [ ] **Outline write-back** — edit Outline-sourced records from the app via Outline API (`capabilities: {"write"}`), keeping Outline as source of truth. (Q13, Q22)
- [ ] **FHIR R4 import/export plugin** — map internal model ↔ FHIR resources (Condition, Procedure, Observation, DiagnosticReport, MedicationStatement, AllergyIntolerance, Immunization, DocumentReference). (Q4)
- [ ] Czech eHealth integrations (e.g. national EHR / eRecept) — *speculative, depends on available APIs*.
- [ ] Webhook trigger for immediate sync (Outline webhooks).
- [ ] OCR / LLM-assisted extraction inside the app (today: via external AI agent over MCP).

## People & sharing
- [ ] **Dependent profiles without a login** (children, elderly parents) — Person without User, managed by owners/editors. Data model already supports it. (Q19)
- [ ] Ownership transfer (e.g. child turns 18).
- [ ] Time-limited shares (e.g. share with a doctor for 7 days).

## 3D & visualization
- [ ] **STL → GLB conversion on upload** for custom overlays. (Q27)
- [ ] **Layered anatomy** — skin / skeleton / organs toggles using Human Reference Atlas (CC BY 4.0) + BodyParts3D (CC BY 4.0); needs alignment to MPFB proportions and `ATTRIBUTION.md`. (Q7, Q35)
- [ ] Child body models / age-adjusted proportions. (Q35)
- [ ] Map regions to SNOMED CT / FMA codes (check national SNOMED licence before shipping data).
- [ ] Heatmap mode (frequency of events per region).

## Imaging & documents
- [ ] DICOM support with embedded viewer (e.g. OHIF / Cornerstone). (Q8)
- [ ] Full-text search inside PDFs.

## Automation
- [ ] Additional MCP tools: `update_draft`, `link_records`, `get_emergency_summary`.
- [ ] Reminders (vaccination boosters, preventive check-ups, medication end dates).

## Known M1 limitations (scheduled)
- [ ] Access-log retention setting is stored but not yet enforced (purge job with scheduler — M5).
- [ ] Orphaned uploads (uploaded in a form that was then cancelled after a crash) are not garbage-collected yet (M5 maintenance job).
- [ ] HEIC is stored but not converted to JPEG for inline preview (M2).
- [ ] Region picker is list-based; click-on-body picking comes with the 3D body (M2).
- [ ] OIDC login with an email that already belongs to a local account links the two (subject stored). Revisit if this is undesirable.
- [ ] Login rate limiting is in-memory (single process) — resets on restart.

## Operations
- [ ] Remote backup targets (S3 / WebDAV / SFTP) — deliberately excluded in v1. (Q29)
- [ ] Postgres support — not planned; revisit only if SQLite limits are hit.
- [ ] Optional app-level encryption at rest.
- [ ] TOTP for local and admin accounts.
