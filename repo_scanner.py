"""Standalone repository scanner script.

Walks /upgrades directory, computes SHA256 for every file,
and syncs Repository/RepositoryFile records to the database.

Runs as a separate Docker container with /upgrades volume mapping.
"""

import hashlib
import logging
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.crud.repository import (
    cleanup_repository_files,
    create_repository,
    upsert_repository_file,
)
from app.db.base import Base
from app.models.repository import Repository

logger = logging.getLogger(__name__)

UPGRADES_DIR = "./upgrades"
REPO_TYPE_MAP = {
    "_microplate": "microplate",
    "_userspace": "userspace",
}


def compute_sha256(filepath: str) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_repos(upgrades_dir: str) -> dict[str, dict[str, list[str]]]:
    """Walk upgrades directory and identify repos by folder structure.

    Returns:
        {repo_name: {repo_type: [filename, ...]}}
    """
    repos: dict[str, dict[str, list[str]]] = {}

    if not os.path.isdir(upgrades_dir):
        logger.warning("Upgrades directory not found: %s", upgrades_dir)
        return repos

    for repo_name in sorted(os.listdir(upgrades_dir)):
        repo_path = os.path.join(upgrades_dir, repo_name)
        if not os.path.isdir(repo_path):
            continue

        repo_types: dict[str, list[str]] = {}

        for entry in sorted(os.listdir(repo_path)):
            type_dir = os.path.join(repo_path, entry)
            if not os.path.isdir(type_dir):
                continue

            if entry not in REPO_TYPE_MAP:
                continue

            repo_type = REPO_TYPE_MAP[entry]
            filenames = []

            for filename in sorted(os.listdir(type_dir)):
                file_path = os.path.join(type_dir, filename)
                if not os.path.isfile(file_path):
                    continue
                filenames.append(filename)

            if filenames:
                repo_types[repo_type] = filenames

        if repo_types:
            repos[repo_name] = repo_types

    return repos


def sync_repo_to_db(
    db, repo_name: str, repo_type: str, filenames: list[str]
) -> None:
    """Sync a single repo type to the database."""
    # Get or create repository
    repo = None
    for r in db.query(Repository).filter(
        Repository.name == repo_name, Repository.repo_type == repo_type
    ).all():
        repo = r
        break

    if repo is None:
        repo = create_repository(
            db,
            __import__("app.schemas.repository", fromlist=["RepositoryCreate"])
            .RepositoryCreate(name=repo_name, repo_type=repo_type),
        )
        logger.info("Created repository: %s (%s)", repo_name, repo_type)
    else:
        logger.info("Found existing repository: %s (%s)", repo_name, repo_type)

    # Upsert files
    existing_filenames: set[str] = set()
    for filename in filenames:
        file_path_arg = _get_file_path(repo_name, repo_type, filename)
        try:
            sha256 = compute_sha256(file_path_arg)
            upsert_repository_file(db, repo.id, filename, sha256)
            existing_filenames.add(filename)
        except (OSError, PermissionError) as e:
            logger.error(
                "Error reading file %s/%s/%s: %s",
                repo_name,
                repo_type,
                filename,
                e,
            )

    # Clean up deleted files
    deleted_count = cleanup_repository_files(
        db, repo.id, existing_filenames
    )
    if deleted_count > 0:
        logger.info(
            "Removed %d deleted file records for %s (%s)",
            deleted_count,
            repo_name,
            repo_type,
        )


def _get_file_path(repo_name: str, repo_type: str, filename: str) -> str:
    """Build file path from repo name, type, and filename."""
    # Reverse the type mapping to get directory name
    type_dir = f"_{repo_type}"
    return os.path.join(UPGRADES_DIR, repo_name, type_dir, filename)


def main() -> None:
    """Main scanner entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logger.info("Starting repository scan of %s", UPGRADES_DIR)

    # Create database engine and session
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        repos = discover_repos(UPGRADES_DIR)

        if not repos:
            logger.info("No repositories found in %s", UPGRADES_DIR)
            return

        logger.info("Discovered %d repositories", len(repos))

        for repo_name, repo_types in repos.items():
            for repo_type, filenames in repo_types.items():
                logger.info(
                    "Syncing %s (%s): %d files",
                    repo_name,
                    repo_type,
                    len(filenames),
                )
                sync_repo_to_db(db, repo_name, repo_type, filenames)

        logger.info("Repository scan complete")
    except Exception:
        logger.exception("Scanner failed")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
