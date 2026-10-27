# Anamnesis — Specification (v1)

> Self-hosted, local-first app to visualize and manage a person's medical history on a 3D body.
> **Not a medical device. Not medical advice.**

Status: draft agreed in design interview (2026-10-27). Decision references (`Q#`) are listed in §17.

---

## 1. Goals & non-goals

**Goals**
- One place for a person's conditions, procedures, exams, lab values, medications, allergies, vaccinations and documents.
- Visualize *where* on the body things happened and *when* (3D body + timeline).
- Pluggable input sources (Outline, folders, …) plus native in-app records.
- AI-assisted entry via MCP, always with human review.
- Runs as a single Docker container on a home server / NAS.

**Non-goals (v1)**
- Clinical / multi-tenant use by doctors or clinics.
- Internet-facing deployment (possible, but explicitly discouraged — see §12).
- DICOM imaging viewer, two-way sync with external sources, child body models (see `BACKLOG.md`).

## 2. Principles

1. **Local first.** LAN by default; no telemetry; no external calls except configured sources/OIDC.
2. **One source of truth per record.** Imported records are read-only in the app; native records are owned by the app. (Q3, Q13, Q22)
3. **Human in the loop.** Anything created by AI/API is a draft until a person confirms it. (Q40)
4. **Standards-shaped, not standards-bound.** Internal model borrows FHIR R4 concepts and codes; full FHIR only at the edges via a future plugin. (Q4)
5. **User owns their data.** Backups and export are first-class; storage is plain files + SQLite.

## 3. Users, persons, roles

### 3.1 Entities
- **User** — a login identity (email = username).
- **Person** — a patient profile with medical data.
- v1: **every User has exactly one Person** (1:1), but they are **separate tables** so profiles without a login (children, dependents) can be added later without a migration. (Q11, Q19)
- **Admin** — a separate, non-patient account. Has no Person, sees no medical data. (Q11, Q21)

### 3.2 Sharing (Q11, Q41)
- An owner shares their Person with another user by email, with role:
  - **viewer** — read everything.
  - **editor** — read + create/edit/delete *native* records, manage sources for that Person.
- Editors **cannot** re-share, change sharing, or delete the profile.
- If the email has no account yet, the share is **pending** and activates on first login with that email.
- Owner can revoke any share at any time.
- Share dialog: free-text email entry. If the admin enables *"Allow user directory in share dialog"* (default **off**), the dialog also offers a searchable list of existing users.
- Ownership transfer: not in v1.

### 3.3 Authentication (Q12, Q20, Q21)
| Account type | How created | How logs in |
|---|---|---|
| OIDC user | Auto-provisioned on first successful OIDC login (email claim = username) | `/login` → OIDC provider |
| Local user | Created by admin in Admin UI | `/login` → email + password |
| Admin | Seeded from `.env` on startup | Separate URL, default `/admin/login` |

- Access control for OIDC is delegated to the IdP's allow-list (e.g. tinyauth, Authentik, Authelia). Anamnesis does not add its own allow-list in v1.
- Passwords: Argon2id. Sessions: HTTP-only, `SameSite=Lax`, `Secure` when behind HTTPS.
- OIDC: Authorization Code + PKCE; `email` claim required; `email_verified` respected if present.
- Users can create **personal access tokens** (PATs) for REST/MCP (§8).

### 3.4 Permissions matrix
| Action | Owner | Editor | Viewer | Admin |
|---|---|---|---|---|
| View records / dashboard | ✔ | ✔ | ✔ | ✘ |
| Create/edit/delete native records | ✔ | ✔ | ✘ | ✘ |
| Confirm drafts | ✔ | ✔ | ✘ | ✘ |
| Configure sources | ✔ | ✔ | ✘ | ✘ |
| Share / revoke | ✔ | ✘ | ✘ | ✘ |
| Emergency card config | ✔ | ✔ | ✘ | ✘ |
| View access log | ✔ | ✘ | ✘ | ✘ |
| Manage user accounts, backups, settings | ✘ | ✘ | ✘ | ✔ |

## 4. Data model

FHIR-shaped, simplified. All IDs are UUIDv7. All timestamps UTC; dates may be partial (`2019`, `2019-05`, `2019-05-14`).

### 4.1 Common record fields
| Field | Req. | Notes |
|---|---|---|
| `id` | auto | UUID |
| `person_id` | auto | owner Person |
| `type` | ✔ | `condition` · `procedure` · `exam` · `observation` · `medication` · `allergy` · `vaccination` · `document` |
| `title` | ✔ | short human title |
| `date` | ✔ | event / start date (partial allowed) |
| `end_date` | | for ranges |
| `regions` | type-dependent | list of region refs (§5); default `systemic` if empty and required |
| `codes` | | `[{system: icd10|snomed|loinc|atc|custom, code, display}]` |
| `description` | | Markdown |
| `attachments` | | list of file refs (§10) |
| `model_overlay` | | custom GLB overlay (§10.2) |
| `links` | | related record IDs (e.g. procedure → condition) |
| `facility`, `practitioner` | | free text |
| `tags` | | free-form strings |
| `status` | type-dependent | see per-type |
| `review_state` | auto | `confirmed` · `draft` (§8.3) |
| `origin` | auto | `native` or `source:<source_id>` |
| `provenance` | auto | created/updated by user / token / plugin, timestamps, raw-payload hash for imports |
| `deleted_at` | auto | soft delete |

### 4.2 Types, required & optional fields (Q16, Q30b)
Every type requires `type`, `title`, `date`. Additional:

| Type | Required | Optional (examples) |
|---|---|---|
| condition | `status` (`active`/`resolved`/`remission`) | `end_date`, ICD-10, `severity`, `regions` |
| procedure | `regions` | facility, practitioner, `outcome`, `implants[]`, linked condition |
| exam | `kind` (`imaging`/`specialist`/`preventive`/`emergency`/`other`) | `findings`, `regions`, facility, practitioner |
| observation | `name`, `value`, `unit` | `reference_range {low, high, text}`, LOINC, `method`, `interpretation` |
| medication | `name`, `status` (`active`/`stopped`) | `dose`, `frequency`, `end_date`, `reason` (link), ATC |
| allergy | `substance`, `criticality` (`low`/`high`/`unknown`) | `reaction`, `onset` |
| vaccination | `vaccine` | `dose_number`, `batch`, facility |
| document | `file` | linked record, `regions` |

Person-level fields (not records): name, date of birth, sex, **body model** (`male`/`female`, independent of sex), blood type, emergency contacts, organ-donation statement, preferred language. (Q35, Q34)

Full YAML schema + examples: [`docs/medrecord-schema.md`](docs/medrecord-schema.md).

### 4.3 Versioning
- Every change (native edit or source sync) writes a row in `record_versions` (full JSON snapshot + actor + timestamp).
- Imported records keep the raw source payload + hash for re-parsing when a plugin improves.

## 5. Body regions (Q6, Q17)

- Own hierarchical vocabulary, ~75 regions (draft, extensible), with laterality where relevant, optional SNOMED/FMA mapping later.
- Region ref syntax: `"<region_id>"` or `"<region_id>:<left|right|both>"`; lateral regions **require** a side.
- Optional precise point: `{region: "knee:left", offset: [x, y, z]}` — offset in normalized region-local space (`-1..1`), so it survives model swaps.
- Pseudo-regions: `systemic` (whole body / no location, e.g. blood tests, hypertension), `skin` (whole surface).
- Internal organs are **projected** to their surface area in v1 (layered anatomy in backlog).
- Draft list: [`docs/regions.md`](docs/regions.md). The GLB mesh names must equal region IDs.

## 6. Sources (input plugins) (Q5, Q14, Q15, Q22, Q25, Q26)

### 6.1 Plugin interface
In-process Python packages, discovered via entry point group `anamnesis.sources`, loadable from a `/config/plugins` volume. **Plugins run with full app privileges — install only trusted plugins.**

```python
class SourcePlugin(Protocol):
    id: str                      # "outline", "folder"
    name: str
    config_schema: dict          # JSON Schema → rendered as settings form
    capabilities: set[str]       # {"read"}  ("write" reserved for future)

    def validate_config(self, config: dict) -> None: ...
    def browse(self, config: dict, path: str | None) -> list[BrowseNode]: ...   # tree picker
    def fetch(self, config: dict, since: datetime | None) -> Iterable[RawItem]: ...
    def parse(self, item: RawItem) -> ParseResult: ...  # normalized records + attachments, or error
```

- A **source instance** = plugin + config + bound Person (+ chosen tree/path). Configured by the Person's owner or editor.
- Imported records are **read-only** in the app (no edits, no annotations). The detail view shows *"Open in <source>"*.
- Items that fail to parse are listed under *Source → Issues* with the error; never silently dropped.

### 6.2 Sync
- Per-instance interval (default **15 min**) + manual *Sync now*.
- Upsert by `(source_id, external_id)`; unchanged hash → skip.
- Item gone from source or moved outside the selected tree → **soft-delete** (hidden, kept in history, purgeable by owner).
- Each sync logged (started, finished, counts, errors).

### 6.3 Built-in plugin: Outline
- Global setting (admin): Outline base URL.
- Per user: own Outline **API token** (stored encrypted with `ANAMNESIS_SECRET_KEY`) — so users can only reach what they can see in Outline. (Q23)
- User picks a collection / document subtree via `browse`. The selected root = that Person.
- **Page format**: one page = one record; first fenced code block with language `medrecord` holds YAML fields; remaining Markdown = `description`; page attachments → cached locally as Documents. Pages without the block are ignored (shown in Issues as *unparsed*, optional). (Q24)
- Template: [`docs/outline-template.md`](docs/outline-template.md).

### 6.4 Built-in plugin: Folder
- Read-only. Config: a path under the mounted `/import` volume, bound to a Person.
- One `*.yaml` / `*.yml` / `*.json` file = one record (same schema as `medrecord`). Sibling files referenced in `attachments` are imported.
- Change detection by mtime + hash.

## 7. Native records & forms (Q30)

- *+ Add record* → choose type → form with **required fields shown**, optional fields added via *+ Add field*.
- Region picker: click on the 3D body (toggle selection) or searchable list; side selector for lateral regions.
- Attachments by drag & drop.
- Native records are fully editable/deletable (soft delete + history).
- Imported records open in the same view, read-only, with source badge.

## 8. Automation: REST API & MCP (Q14, Q39, Q40)

### 8.1 Tokens
- **Personal access tokens**: created in user settings, name + expiry (default 90 days, max 1 year) + optional scope (`read` / `write`). Shown once, stored hashed. Revocable.
- Token acts as its user; only Persons the user can access, with the user's role.

### 8.2 REST API
- `/api/v1/...`, OpenAPI docs at `/api/docs` (authenticated).
- Core endpoints: `persons`, `records` (CRUD for native, read for imported), `records/{id}/attachments`, `regions`, `schema/{type}`, `sources` (+ `sync`), `drafts` (+ `confirm`).

### 8.3 MCP server
- Streamable HTTP at `/mcp`, auth `Authorization: Bearer <PAT>`.
- Tools:

| Tool | Purpose |
|---|---|
| `list_persons` | Persons the user can **edit** |
| `list_regions` | Region vocabulary (ids, labels cs/en, laterality) |
| `get_record_schema(type)` | Required/optional fields, enums, examples |
| `search_records(person_id, query?, type?, from?, to?)` | Avoid duplicates, find links |
| `create_record(person_id, record)` | Always created as **draft** |
| `upload_attachment(person_id, filename, content_base64, record_id?)` | Attach source scans |

- **Drafts**: records created via MCP or API get `review_state: draft` — greyed out in UI, excluded from emergency card and timeline "state" computations. User reviews in the form with the attached scan side-by-side → *Confirm* / edit / discard.
- Provenance stores token name + client info.

## 9. User interface (Q31–Q34, Q42)

### 9.1 Layout
- **Top bar**: Person switcher (me + shared with me, role badge), *+ Add record*, drafts counter, language (cs/en), user menu. *Access log* button — **hidden by default**, enabled in user settings.
- **Desktop**: left = filterable record list · centre = 3D body · right = record detail · bottom = timeline.
- **Mobile**: tabs *Body / List / Timeline*; detail as sheet.

### 9.2 3D body
- Three.js via react-three-fiber. Model per Person: male / female (MPFB, §16).
- **Fixed camera, no zoom, no pan.** User can drag to rotate around the vertical axis only. No preset view buttons.
- Selecting a record (list, timeline, marker) → body **smoothly rotates** (shortest path, eased ~600 ms) to face the region, and the region is **outlined/highlighted**. Multi-region records: face the first, highlight all.
- Markers: colour by record type; active conditions glow/pulse; resolved/old items fade with age; drafts dashed/grey; overlapping records cluster into one marker with a count.
- Clicking a region/marker filters the list to that region (and its children).
- Custom GLB overlays render in place on the default body (§10.2).
- Filters (shared by list/body/timeline): date range, type, status, source, tags, review state.

### 9.3 Timeline
- Horizontal, lanes per type, zoomable in time.
- **Scrubber**: drag to a date → body shows the state *at that date* (active conditions, existing implants, active meds); list filters accordingly.
- **Observation charts**: per observation name, line chart over time with reference-range band; opened from an observation record or a "Labs" view.

### 9.4 Emergency card (Q34)
- Owner/editor picks which fields appear: blood type, allergies, active medications, active conditions, implants/devices, emergency contacts, organ-donation statement.
- Outputs: printable **PDF** (wallet + A4), **lock-screen image** (PNG at common phone resolutions), **QR code that embeds the data itself** (compact text/JSON, no URL — works offline and without exposing the server).
- Drafts are never included. Card shows "generated on <date>".

### 9.5 Access log (Q42)
- Per Person, visible to owner only: who viewed/edited what, when, via UI / API / MCP (token name).
- Retention: 1 year (admin-configurable).

### 9.6 Admin UI (separate app area at `ADMIN_PATH`)
- Users: list, create local user, disable, delete (with Person data deletion confirm), reset local password.
- Settings: Outline base URL, user directory in share dialog (on/off), upload limits (incl. GLB size), access-log retention, default language.
- Backups: schedule, target path, retention, run now, last result, test restore.
- System: version, plugin list, sync health, account-level audit events.

## 10. Files & 3D overlays (Q8, Q27, Q28)

### 10.1 Attachments
- Types v1: PDF, JPEG, PNG, WebP, HEIC (converted to JPEG for display), GLB.
- Stored on filesystem: `/data/files/<person_uuid>/<sha256[0:2]>/<sha256>` + metadata in DB. Per-person folders make export/deletion of one person simple.
- Imported attachments (e.g. Outline) are **cached locally** at sync time.
- Thumbnails/previews generated on upload.
- Encryption at rest: delegated to the host (LUKS / NAS encryption). Documented.

### 10.2 Custom 3D overlay
- Field `model_overlay: {file, anchor_region, offset[3], rotation[3], scale}`.
- GLB is rendered **inside the default body model**, anchored to the region's local frame. Shown when the record is selected (and optionally always, via toggle).
- Size limit set by admin (default 50 MB). STL→GLB conversion: backlog.

## 11. Architecture & deployment (Q10, Q18, Q36)

- **Single image**: Python 3.12 + FastAPI (API, MCP, auth) serving the built React (TypeScript, Vite, react-three-fiber, i18next) SPA. In-process scheduler (APScheduler) for syncs and backups.
- **DB**: SQLite (WAL) via SQLAlchemy 2 + Alembic. Postgres not planned.
- **Volumes**: `/data` (db, files, backups default), `/config` (plugins, optional overrides), `/import` (Folder source, read-only mount recommended).

```yaml
# docker-compose.yml (example)
services:
  anamnesis:
    image: ghcr.io/<org>/anamnesis:latest
    container_name: anamnesis
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:8080"   # bind to LAN IP or reverse proxy; do NOT expose publicly
    env_file: .env
    volumes:
      - ./data:/data
      - ./config:/config
      - /mnt/nas/medical-import:/import:ro
```

```dotenv
# .env
ANAMNESIS_SECRET_KEY=            # 32+ random bytes, base64; encrypts stored tokens & sessions
ANAMNESIS_PUBLIC_URL=http://anamnesis.lan:8080
ANAMNESIS_ADMIN_USERNAME=admin
ANAMNESIS_ADMIN_PASSWORD=        # applied on first start / when changed
ANAMNESIS_ADMIN_PATH=/admin
ANAMNESIS_DEFAULT_LANGUAGE=cs
OIDC_ISSUER=
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_SCOPES=openid email profile
TZ=Europe/Prague
```

## 12. Security (best effort, local-first)

Security is not the top priority, but sensible defaults are mandatory:
- **Docs must clearly discourage internet exposure.** If someone does: reverse proxy with HTTPS, IdP in front, VPN preferred (Tailscale/WireGuard).
- Argon2id passwords; PATs hashed; Outline tokens encrypted (`ANAMNESIS_SECRET_KEY`).
- CSRF protection on cookie-auth endpoints; strict CSP; no third-party CDNs at runtime (all assets bundled).
- Login rate limiting (local + admin login).
- Admin cannot read medical data.
- Uploaded files served with `Content-Disposition` and correct MIME; never executed; size limits.
- Plugins = trusted code (documented).
- Access log per Person; account-level audit log for admin.
- Container runs as non-root; read-only root FS where feasible.

## 13. Internationalization (Q9)
- UI: Czech + English (i18next), per-user preference, admin default.
- Region labels and enums translated; free text stored as entered.
- Dates/units localized for display; stored in ISO / as entered.

## 14. Backups (Q18, Q29)
- Admin-configured schedule (e.g. daily), target = local path (default `/data/backups`, typically a NAS mount), retention (e.g. 7 daily / 4 weekly / 6 monthly).
- Content: consistent SQLite snapshot (online backup API) + files → `.tar.zst`, optionally encrypted with an `age` passphrase/recipient.
- *Run now*, last status, and *Test restore* (restores into a temp dir and runs integrity checks).
- Users are responsible for off-site copies (NAS backup strategy) — documented.
- Per-person export (ZIP: JSON records + files) from user settings.

## 15. Milestones (Q43)
| | Scope |
|---|---|
| **M1 Core** | Auth (OIDC, local, env admin + admin UI basics), User/Person, sharing, native records + forms + list, attachments, cs/en |
| **M2 Body** | MPFB male/female GLB with region meshes, 3D dashboard, rotation/highlight, markers, timeline + scrubber, observation charts, GLB overlays |
| **M3 Sources** | Plugin interface, Folder plugin, Outline plugin + template, sync engine, versions, issues view |
| **M4 Automation** | PATs, REST API, MCP server, draft review flow |
| **M5 Polish** | Emergency card (PDF, lock screen, QR), backups, access log, admin settings, docs incl. security warnings |

## 16. Licensing & assets (Q35, Q37)
- Code: **AGPL-3.0**.
- v1 body models: **MakeHuman / MPFB** (CC0), split into named region meshes in Blender, exported to GLB (Draco/meshopt).
- Future layered anatomy: Human Reference Atlas (NIH 3D, CC BY 4.0), BodyParts3D (CC BY 4.0) — require `ATTRIBUTION.md` in the image. Avoid share-alike sets (Z-Anatomy, Open3DModel) unless accepted.
- Assets live in `assets/models/` with their own LICENSE files.
- Disclaimer in UI footer + README: *not a medical device, not medical advice.*
- Name "Anamnesis" — verify trademark/name collisions before public release.

## 17. Decision log
| Q | Decision |
|---|---|
| Q1 | Multiple patients per instance |
| Q2 | LAN-first; internet exposure possible but discouraged |
| Q3 | System of record for native data + read-only aggregation of sources |
| Q4 | FHIR-shaped custom model; FHIR plugin later |
| Q5 | Sync & cache into local DB with provenance |
| Q6 | Named regions + optional offset |
| Q7 | Surface body v1, extensible to layers |
| Q8 | Structured data + PDFs/images; DICOM later |
| Q9 | Czech + English |
| Q10 | Python/FastAPI + React/Three.js |
| Q11 | User = Patient (1:1); sharing viewer/editor; separate admin |
| Q12 | OIDC auto-provision (email username) + admin-created local users |
| Q13 | External records read-only; native records editable |
| Q14 | In-process plugins + REST push API |
| Q15 | Outline: tree/path picker per Person; native: current Person |
| Q16 | Core types + medication/allergy/vaccination; emergency card |
| Q17 | Own region vocabulary with optional code mapping |
| Q18 | SQLite + scheduled backups |
| Q19 | User/Person separate tables |
| Q20 | OIDC allow-list delegated to IdP |
| Q21 | Admin from `.env`, separate login URL |
| Q22 | No app annotations on imported records |
| Q23 | Per-user Outline tokens |
| Q24 | Outline `medrecord` YAML block + template |
| Q25 | In-app forms + read-only Folder plugin |
| Q26 | 15-min sync, soft delete, version history |
| Q27 | GLB overlays inside default body; STL conversion backlog |
| Q28 | Files on volume, per-person folders, cached imports, host encryption |
| Q29 | Backups to local path only |
| Q30 | Type-specific forms, required + optional fields, click-on-body region picker |
| Q31 | Dashboard layout as §9.1 |
| Q32 | Fixed camera, Y-axis rotation, rotate + outline on select, no preset buttons |
| Q33 | Timeline scrubber + observation charts |
| Q34 | Emergency card PDF / lock screen / data-embedded QR |
| Q35 | MPFB male/female, body model independent of sex |
| Q36 | Single container |
| Q37 | AGPL-3.0 + disclaimer |
| Q38 | Name: Anamnesis |
| Q39 | MCP over Streamable HTTP with PATs |
| Q40 | AI/API records are drafts |
| Q41 | Pending shares; optional admin-enabled user directory |
| Q42 | Owner access log, hidden button by default |
| Q43 | Milestones M1–M5 |
| Q44 | Spec delivered as repo (zip) |
