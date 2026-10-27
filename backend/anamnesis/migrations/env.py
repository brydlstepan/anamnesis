from alembic import context
from sqlalchemy import create_engine

from anamnesis import models  # noqa: F401  (registers tables)
from anamnesis.db import Base

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    from anamnesis.config import Settings

    url = config.get_main_option("sqlalchemy.url") or Settings().db_url
    with create_engine(url).connect() as conn:
        _run(conn)
        conn.commit()


run_migrations_online()
