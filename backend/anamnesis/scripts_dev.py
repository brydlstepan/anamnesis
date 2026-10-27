"""Developer helpers (not used at runtime)."""

import tempfile
from pathlib import Path

from alembic import command

from .db import make_engine
from .migrate import alembic_config, run_migrations


def make_migration(message: str) -> None:
    """Autogenerate a new Alembic revision by diffing models against a DB at current head."""
    if not message:
        raise SystemExit('usage: make migration m="describe change"')
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(f"sqlite:///{Path(tmp) / 'head.db'}")
        run_migrations(engine)
        cfg = alembic_config()
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.revision(cfg, message=message, autogenerate=True)
