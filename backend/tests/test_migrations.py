from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from anamnesis.db import Base, make_engine
from anamnesis.migrate import run_migrations


def test_migrations_match_models(tmp_path):
    """Fails when models change without a new migration (run `make migration` to create one)."""
    engine = make_engine(f"sqlite:///{tmp_path / 'm.db'}")
    run_migrations(engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff
