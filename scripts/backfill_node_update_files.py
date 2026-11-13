"""Backfill per-file progress rows (node_update_files) for legacy sessions.

Sessions created before the progress tracking change store their progress
as JSON string lists on the node_updates row (fetched_files /
validated_files). This one-off script moves that data into node_update_files
rows (status per old-list membership, timestamps NULL — the exact times are
not recoverable) and optionally drops the two legacy columns.

Standalone script (standalone-db-bootstrap standard): builds its own engine
from settings.database_url — never reuses the app's SessionLocal.

Safe to re-run: sessions that already have progress rows are skipped.

Usage:
    DATABASE_URL=mysql://... python scripts/backfill_node_update_files.py
    ... --drop-old-columns   # also ALTER TABLE node_updates DROP COLUMN
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Standalone script: make the repo root importable regardless of CWD.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import create_engine, inspect, select, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.migrate import run_migrations  # noqa: E402
from app.models.node_update_file import NodeUpdateFile  # noqa: E402

logger = logging.getLogger(__name__)

LEGACY_COLUMNS = ("fetched_files", "validated_files")


def _load_list(value) -> list[str]:
    """Legacy JSON columns arrive as strings on MySQL and SQLite alike."""
    if value is None:
        return []
    if isinstance(value, str):
        value = json.loads(value or "[]")
    return list(value)


def backfill(db, engine, drop_old_columns: bool) -> None:
    """Move legacy JSON-list progress data into node_update_files rows."""
    node_update_cols = {
        c["name"] for c in inspect(engine).get_columns("node_updates")
    }
    has_fetched = "fetched_files" in node_update_cols
    has_validated = "validated_files" in node_update_cols

    cols = ["id", "files"]
    if has_fetched:
        cols.append("fetched_files")
    if has_validated:
        cols.append("validated_files")
    # The ORM no longer maps the legacy columns — read them as raw SQL.
    rows = db.execute(text(f"SELECT {', '.join(cols)} FROM node_updates"))
    backfilled = 0
    skipped = 0
    for row in rows:
        data = dict(zip(cols, row))
        session_id = data["id"]
        files = _load_list(data.get("files"))
        fetched = _load_list(data.get("fetched_files")) if has_fetched else []
        validated = (
            _load_list(data.get("validated_files")) if has_validated else []
        )

        existing = (
            db.execute(
                select(NodeUpdateFile.id)
                .where(NodeUpdateFile.node_update_id == session_id)
                .limit(1)
            )
            .scalars()
            .first()
        )
        if existing is not None:
            skipped += 1
            continue

        # Ordered union (files first), de-duped.
        names = list(dict.fromkeys([*files, *fetched, *validated]))
        for filename in names:
            if filename in validated:
                status = "validated"
            elif filename in fetched:
                status = "fetched"
            else:
                status = "pending"
            db.add(
                NodeUpdateFile(
                    node_update_id=session_id,
                    filename=filename,
                    status=status,
                )
            )
        backfilled += 1
    db.commit()
    logger.info(
        "Backfilled %d session(s), skipped %d already-populated",
        backfilled,
        skipped,
    )

    if drop_old_columns:
        for col in LEGACY_COLUMNS:
            if col in node_update_cols:
                # One ALTER per column: portable across SQLite/MySQL.
                db.execute(text(f"ALTER TABLE node_updates DROP COLUMN {col}"))
                db.commit()
                logger.info("Dropped legacy column node_updates.%s", col)
            else:
                logger.info("Legacy column %s absent — nothing to drop", col)


def main() -> None:
    """Backfill entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill node_update_files rows from legacy sessions."
    )
    parser.add_argument(
        "--drop-old-columns",
        action="store_true",
        help="drop fetched_files/validated_files from node_updates",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not settings.database_url:
        logger.error("settings.database_url is empty — nothing to do")
        sys.exit(1)

    engine = create_engine(settings.database_url)
    run_migrations()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        backfill(db, engine, drop_old_columns=args.drop_old_columns)
        logger.info("Backfill complete")
    except Exception:
        logger.exception("Backfill failed")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
