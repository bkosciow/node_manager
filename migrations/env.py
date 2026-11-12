"""Alembic environment — SPEC-005.

URL resolution: an explicit `sqlalchemy.url` in alembic.ini wins; otherwise
fall back to `settings.database_url` (`.env` / env var) so the app and the
migrations share one URL source. `target_metadata` is `Base.metadata` with
the model barrel imported, so autogenerate diffs against every table.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

from app.config import settings
from app.db.base import Base

# Import the model barrel so Base.metadata knows every registered table.
# flake8: noqa: F401
import app.models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model MetaData for 'autogenerate' support — diffs models vs live schema.
target_metadata = Base.metadata


def _url() -> str:
    """Explicit ini `sqlalchemy.url` wins; else settings.database_url."""
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
