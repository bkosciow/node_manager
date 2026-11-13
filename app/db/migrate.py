import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import settings

logger = logging.getLogger(__name__)

# app/db/migrate.py -> app/db -> app -> repo root (or /app inside the image).
# Anchoring here keeps this CWD-independent, per SPEC-005.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


def run_migrations() -> None:
    """Run `alembic upgrade head` in-process; no-op when schema is current.

    The URL always comes from settings.database_url (single source of
    truth); alembic.ini ships with sqlalchemy.url intentionally empty.
    """
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    logger.info("alembic upgrade head complete (schema at head)")
