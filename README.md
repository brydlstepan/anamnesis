# Anamnesis

Self-hosted, local-first Docker app to visualize and manage a person's medical history on an interactive 3D body.

> ⚠️ **Not a medical device. Not medical advice.**
> ⚠️ **Designed for LAN use. Do not expose it to the internet.** If you must, put it behind HTTPS, your identity provider and preferably a VPN — at your own risk.

**Status:** M1 (Core) skeleton — auth (OIDC / local / env admin), profiles, sharing, native records with forms, attachments, cs/en UI, admin UI. The 3D body arrives in M2.

## Quick start (Docker)
```bash
cp .env.example .env          # set ANAMNESIS_SECRET_KEY and ANAMNESIS_ADMIN_PASSWORD (min. 12 chars)
mkdir -p data config && sudo chown 1000:1000 data config
docker compose up -d --build
```
- App: http://localhost:8080 · Admin: http://localhost:8080/admin → create users (or configure OIDC).
- **Back up `./data`** (database + files). Encrypt the disk it lives on.
- Developers: see [docs/development.md](docs/development.md).

| Document | Content |
|---|---|
| [SPEC.md](SPEC.md) | Full v1 specification and decision log |
| [BACKLOG.md](BACKLOG.md) | Deferred features |
| [docs/medrecord-schema.md](docs/medrecord-schema.md) | Record schema (YAML/JSON) with examples per type |
| [docs/regions.md](docs/regions.md) | Body-region vocabulary (draft) |
| [docs/outline-template.md](docs/outline-template.md) | Outline page template for the Outline source |

## Highlights
- Multi-user, each user is a patient; share your profile as viewer or editor.
- 3D body dashboard with markers, timeline scrubber ("body at date X") and lab charts.
- Input plugins: Outline, Folder (read-only sources) + in-app forms (native records).
- REST API + MCP server — let an AI agent draft records from scanned reports; you confirm.
- Emergency card: PDF, lock-screen image, offline QR.
- Single container, SQLite, scheduled backups.

## License
AGPL-3.0 (code) — add the official license text as `LICENSE` (GitHub → *Add file → Create new file → LICENSE → choose template*). 3D assets carry their own licenses in `assets/models/`.
