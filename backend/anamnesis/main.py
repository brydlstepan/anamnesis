"""Application factory: `uvicorn anamnesis.main:create_app --factory`."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from . import __version__
from .config import Settings
from .db import make_engine
from .migrate import run_migrations
from .routers import admin, attachments, auth, persons, records
from .security import LoginRateLimiter

log = logging.getLogger("anamnesis")

CSRF_HEADER = b"x-requested-with"
CSRF_VALUE = b"anamnesis"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; worker-src 'self' blob:; connect-src 'self'; object-src 'none'; "
    "frame-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class SecurityMiddleware:
    """CSRF guard for cookie-authenticated API calls + security headers on every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        if scope["method"] not in SAFE_METHODS and path.startswith("/api/"):
            headers = dict(scope["headers"])
            if headers.get(CSRF_HEADER) != CSRF_VALUE:
                await JSONResponse({"detail": "Missing CSRF header"}, status_code=403)(scope, receive, send)
                return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                hdrs = message.setdefault("headers", [])
                existing = {k.lower() for k, _ in hdrs}
                defaults = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    (b"content-security-policy", CSP.encode()),
                ]
                hdrs.extend((k, v) for k, v in defaults if k not in existing)
            await send(message)

        await self.app(scope, receive, send_with_headers)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    engine = make_engine(settings.db_url)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.files_dir.mkdir(parents=True, exist_ok=True)
        run_migrations(engine)  # single process → safe to migrate on start
        with SessionLocal() as db:
            admin.seed_admin(db, settings)
        if not settings.public_url.startswith("https://"):
            log.info("Running on plain HTTP (%s) — fine on a LAN; never expose this to the internet.",
                     settings.public_url)
        yield
        engine.dispose()

    docs = settings.enable_api_docs
    app = FastAPI(
        title="Anamnesis",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = SessionLocal
    app.state.rate_limiter = LoginRateLimiter()
    app.state.oauth = None

    if settings.oidc_enabled:
        from authlib.integrations.starlette_client import OAuth

        oauth = OAuth()
        oauth.register(
            "oidc",
            server_metadata_url=settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration",
            client_id=settings.oidc_client_id,
            client_secret=settings.oidc_client_secret,
            client_kwargs={"scope": settings.oidc_scopes, "code_challenge_method": "S256"},
        )
        app.state.oauth = oauth

    app.add_middleware(SecurityMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="anamnesis_session",
        max_age=settings.session_max_age_days * 86400,
        same_site="lax",
        https_only=settings.secure_cookies,
    )

    for r in (auth.router, persons.router, records.router, attachments.router, admin.router):
        app.include_router(r)

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def api_not_found(rest: str):
        raise HTTPException(404, "Not found")

    _mount_spa(app, settings.static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: Path | None) -> None:
    """Serve the built React SPA; every non-API path falls back to index.html (client-side routing)."""
    if static_dir is None or not (static_dir / "index.html").is_file():
        log.info("No built frontend found (ANAMNESIS_STATIC_DIR) — serving API only")
        return
    index = static_dir / "index.html"
    if (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    root = static_dir.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = (static_dir / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
