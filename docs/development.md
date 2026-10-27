# Development

## Layout
```
backend/            FastAPI app (package `anamnesis`)
  anamnesis/
    main.py         app factory, security middleware, SPA serving
    config.py       env settings
    models.py       SQLAlchemy models (User, Person, Share, Record, …)
    record_types.py record types + required/optional fields (drives API validation AND the UI form)
    regions.py      region vocabulary helpers (data/regions.json ← docs/regions.md)
    routers/        auth, persons+sharing, records, attachments, admin
    migrations/     Alembic (applied automatically on startup)
  tests/            pytest
frontend/           React + Vite + TypeScript, i18n cs/en
  src/user/         patient UI (dashboard, record form, settings)
  src/admin/        admin UI (served under ANAMNESIS_ADMIN_PATH)
scripts/            gen_regions.py
```

## Run locally
```bash
make setup
cat > .env.dev <<'ENV'
ANAMNESIS_SECRET_KEY=dev-secret-change-me-dev-secret-change-me
ANAMNESIS_ADMIN_PASSWORD=admin-password-123
ANAMNESIS_DATA_DIR=./data
ANAMNESIS_PUBLIC_URL=http://localhost:5173
ANAMNESIS_ENABLE_API_DOCS=true
ENV
make dev-backend      # :8080
make dev-frontend     # :5173 → open http://localhost:5173 (admin: /admin)
```
To test the production bundle without Vite: `make build` and add `ANAMNESIS_STATIC_DIR=./frontend/dist` to `.env.dev`.

## Tests & lint
```bash
make test   # pytest — includes a check that migrations match the models
make lint   # ruff + tsc
```

## Changing the data model
1. Edit `backend/anamnesis/models.py`.
2. `make migration m="what changed"` → review the generated file in `migrations/versions/`.
3. `make test`.

## Adding a record field
Add it to `TYPE_FIELDS` (or `COMMON_TAIL`) in `record_types.py`, plus labels in `frontend/src/locales/{cs,en}.json` (`fields.<name>`, and `enum.<value>` for enum options). The form renders it automatically.

## Editing body regions
Edit `docs/regions.md`, then `make regions`. Region ids are stable identifiers used in records and as mesh names in the 3D models — never rename an id that is in use.

## Security conventions
- Every unsafe API request must send `X-Requested-With: anamnesis` (CSRF guard); `frontend/src/lib/api.ts` does this.
- Access to a person always goes through `deps.load_person()` → 404 when no access (no enumeration).
- Imported records (`origin != "native"`) are read-only.
- Uploaded files are type-sniffed by magic bytes, stored per person, served with a sandbox CSP.
- The admin API never returns medical data.

## Docker
```bash
cp .env.example .env    # fill in secret + admin password
mkdir -p data config && sudo chown 1000:1000 data config   # container runs as uid 1000
docker compose up -d --build
```
Build args `UID`/`GID` change the container user if your NAS needs a different owner.
