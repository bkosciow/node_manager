import logging
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy import pool
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger(__name__)

# app/db/migrate.py -> app/db -> app -> repo root (or /app inside the image).
# Anchoring here keeps this CWD-independent, per SPEC-005.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"

# Named MySQL advisory lock that serializes concurrent in-process upgrades
# across containers (GET_LOCK names are capped at 64 chars in MySQL).
_MIGRATION_LOCK = "node_manager_alembic"
# Max seconds a container waits for a peer to finish a migration before giving
# up; on timeout it raises so the container fails startup and is retried by
# the restart policy (never two concurrent `upgrade head` runs).
_MIGRATION_LOCK_TIMEOUT_S = 120


@contextmanager
def _serialized_upgrade(url: str):
    """Hold a MySQL advisory lock across the body so only one container
    applies migrations at a time.

    Two containers that start at once (api + scanner) would otherwise both run
    `upgrade head` on a fresh DB and race on CREATE TABLE; the loser errors
    out and must restart. With the lock, the second blocks until the first is
    done, then finds the schema already at head (a clean no-op). Non-MySQL
    URLs (e.g. the throwaway SQLite the tests use) skip the lock — those are
    single-process and have no cross-container race.
    """
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        if engine.dialect.name != "mysql":
            yield
            return
        with engine.connect() as conn:
            acquired = conn.execute(
                text("SELECT GET_LOCK(:name, :timeout)"),
                {"name": _MIGRATION_LOCK, "timeout": _MIGRATION_LOCK_TIMEOUT_S},
            ).scalar()
            if acquired != 1:
                raise RuntimeError(
                    f"could not acquire migration lock '{_MIGRATION_LOCK}' "
                    f"within {_MIGRATION_LOCK_TIMEOUT_S}s (a peer migration is "
                    "running or the lock failed)"
                )
            try:
                yield
            finally:
                conn.execute(
                    text("SELECT RELEASE_LOCK(:name)"),
                    {"name": _MIGRATION_LOCK},
                )
    finally:
        engine.dispose()


def run_migrations() -> None:
    """Run `alembic upgrade head` in-process; no-op when schema is current.

    The URL always comes from settings.database_url (single source of
    truth); alembic.ini ships with sqlalchemy.url intentionally empty. A
    MySQL advisory lock (see _serialized_upgrade) serializes concurrent
    startup runs across containers.
    """
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    with _serialized_upgrade(settings.database_url):
        command.upgrade(cfg, "head")
    logger.info("alembic upgrade head complete (schema at head)")
