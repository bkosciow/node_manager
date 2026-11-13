"""Standalone repository scanner CLI.

Thin wrapper around the shared scan core in
``app/services/repo_scan.py`` (also used by the REST API's force-rescan
endpoint and the in-app auto-scanner). Keeps the standalone DB bootstrap:
own engine + ``run_migrations()`` + one session for the whole run (the
standalone-db-bootstrap standard, updated by SPEC-005).

Runs as a separate Docker container with a /upgrades volume mapping.
"""

import logging
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.migrate import run_migrations
from app.services.repo_scan import (
    compute_sha256,
    discover_repos,
    scan_all,
    scan_repo,
)

logger = logging.getLogger(__name__)

__all__ = [
    "compute_sha256",
    "discover_repos",
    "main",
    "scan_all",
    "scan_repo",
    "sync_repo_to_db",
]


def sync_repo_to_db(
    db: Session, repo_name: str, repo_type: str, filenames: list[str]
) -> None:
    """Legacy alias of ``scan_repo`` — kept for import compatibility."""
    scan_repo(db, repo_name, repo_type, filenames)


def main() -> None:
    """Main scanner entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logger.info("Starting repository scan of %s", settings.upgrades_dir)

    # Standalone bootstrap: own engine, one session for the run; schema via
    # Alembic (SPEC-005 — create_all retired from app code paths).
    engine = create_engine(settings.database_url)
    run_migrations()
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = session_local()
    try:
        reports = scan_all(db)
        if not reports:
            logger.info("No repositories found in %s", settings.upgrades_dir)
        else:
            logger.info(
                "Discovered %d repository type(s), %d error(s)",
                len(reports),
                sum(report.errors for report in reports),
            )
        logger.info("Repository scan complete")
    except Exception:
        logger.exception("Scanner failed")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
