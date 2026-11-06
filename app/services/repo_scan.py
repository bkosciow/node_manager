"""Shared repository scan core.

Extracted from the standalone ``repo_scanner.py`` CLI so the REST API
(force-rescan endpoint) and the in-app auto-scanner share one disk-to-DB
sync implementation (see the repo-sync-semantics standard):

- SHA256 is chunked (8 KB reads); a per-file ``OSError`` is logged and the
  scan continues — one unreadable file never aborts the whole run;
- the DB file list mirrors the on-disk directory (upsert + cleanup);
- an empty file list is a no-op (no-wipe guard): no upserts, no cleanup,
  so a missing or emptied directory can never wipe repository records.
"""

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.crud.repository import (
    cleanup_repository_files,
    create_repository,
    upsert_repository_file,
)
from app.db.session import SessionLocal
from app.models.repository import Repository, RepositoryFile
from app.schemas.repository import RepositoryCreate

logger = logging.getLogger(__name__)

REPO_TYPE_MAP = {
    "_microplate": "microplate",
    "_userspace": "userspace",
}


@dataclass
class RepoScanReport:
    """Outcome of one ``scan_repo`` run for a single repository type."""

    repo_name: str
    repo_type: str
    files_found: int      # files enumerated on disk
    files_added: int      # new RepositoryFile rows
    files_updated: int    # existing row, hash changed
    files_unchanged: int  # existing row, hash identical
    files_removed: int    # rows deleted by cleanup
    errors: int           # per-file OSError count (scan continues)


def compute_sha256(filepath: str) -> str:
    """Compute SHA256 hash of a file (chunked 8 KB reads)."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_repos(
    upgrades_dir: str | None = None,
) -> dict[str, dict[str, list[str]]]:
    """Walk the upgrades directory and identify repos by folder structure.

    ``upgrades_dir`` defaults to ``settings.upgrades_dir``. A missing
    directory returns ``{}`` with a warning — the auto-scanner re-checks
    every tick, so a late mount heals without a restart.

    Returns:
        {repo_name: {repo_type: [filename, ...]}}
    """
    if upgrades_dir is None:
        upgrades_dir = settings.upgrades_dir
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
            filenames = [
                filename
                for filename in sorted(os.listdir(type_dir))
                if os.path.isfile(os.path.join(type_dir, filename))
            ]

            if filenames:
                repo_types[repo_type] = filenames

        if repo_types:
            repos[repo_name] = repo_types

    return repos


def list_repo_files_on_disk(repo_name: str, repo_type: str) -> list[str]:
    """List files in ``{upgrades_dir}/{repo_name}/_{repo_type}/``.

    Returns ``[]`` when the directory is absent or holds no files.
    """
    type_dir = os.path.join(settings.upgrades_dir, repo_name, f"_{repo_type}")
    if not os.path.isdir(type_dir):
        return []
    return [
        filename
        for filename in sorted(os.listdir(type_dir))
        if os.path.isfile(os.path.join(type_dir, filename))
    ]


def _file_path(repo_name: str, repo_type: str, filename: str) -> str:
    """Build the on-disk path for a repository file."""
    return os.path.join(settings.upgrades_dir, repo_name, f"_{repo_type}", filename)


def _get_or_create_repository(
    db: Session, repo_name: str, repo_type: str
) -> Repository:
    stmt = select(Repository).where(
        Repository.name == repo_name, Repository.repo_type == repo_type
    )
    repo = db.execute(stmt).scalar_one_or_none()
    if repo is None:
        repo = create_repository(
            db, RepositoryCreate(name=repo_name, repo_type=repo_type)
        )
        logger.info("Created repository: %s (%s)", repo_name, repo_type)
    else:
        logger.debug("Found existing repository: %s (%s)", repo_name, repo_type)
    return repo


def _existing_hashes(db: Session, repo_id: int, filenames: list[str]) -> dict[str, str]:
    """Existing sha256 per filename (rows without a match are absent)."""
    stmt = select(RepositoryFile.filename, RepositoryFile.sha256).where(
        RepositoryFile.repository_id == repo_id,
        RepositoryFile.filename.in_(filenames),
    )
    rows = db.execute(stmt).all()
    return {filename: sha256 for filename, sha256 in rows}


def scan_repo(
    db: Session, repo_name: str, repo_type: str, filenames: list[str]
) -> RepoScanReport:
    """Sync one repository type to the database, mirroring the on-disk state.

    Unreadable files are counted in ``errors`` (the scan continues) and are
    left out of the cleanup set, so their rows are deleted in this run and
    re-added on the next successful scan. An empty ``filenames`` list is a
    no-op (no upserts, no cleanup) — a missing directory must never wipe
    existing records.
    """
    if not filenames:
        logger.warning(
            "No files on disk for %s (%s); skipping sync (no-wipe guard)",
            repo_name,
            repo_type,
        )
        return RepoScanReport(repo_name, repo_type, 0, 0, 0, 0, 0, 0)

    repo = _get_or_create_repository(db, repo_name, repo_type)
    old_hashes = _existing_hashes(db, repo.id, filenames)

    added = updated = unchanged = errors = 0
    hashed: set[str] = set()
    for filename in filenames:
        try:
            sha256 = compute_sha256(_file_path(repo_name, repo_type, filename))
        except (OSError, PermissionError) as exc:
            logger.error(
                "Error reading file %s/%s/%s: %s",
                repo_name,
                repo_type,
                filename,
                exc,
            )
            errors += 1
            continue
        old_hash = old_hashes.get(filename)
        if old_hash is None:
            added += 1
        elif old_hash != sha256:
            updated += 1
        else:
            unchanged += 1
        upsert_repository_file(db, repo.id, filename, sha256)
        hashed.add(filename)

    removed = cleanup_repository_files(db, repo.id, hashed)
    if removed > 0:
        logger.info(
            "Removed %d deleted file records for %s (%s)",
            removed,
            repo_name,
            repo_type,
        )

    logger.info("Scanned %s (%s): %d file(s)", repo_name, repo_type, len(filenames))
    return RepoScanReport(
        repo_name=repo_name,
        repo_type=repo_type,
        files_found=len(filenames),
        files_added=added,
        files_updated=updated,
        files_unchanged=unchanged,
        files_removed=removed,
        errors=errors,
    )


def scan_all(db: Session) -> list[RepoScanReport]:
    """Re-hash every discovered repository type; one report per type."""
    reports: list[RepoScanReport] = []
    for repo_name, repo_types in discover_repos().items():
        for repo_type, filenames in repo_types.items():
            reports.append(scan_repo(db, repo_name, repo_type, filenames))
    return reports


def start_auto_scan(interval_minutes: int) -> None:
    """Spawn the daemon auto-scanner thread; non-positive intervals disable it.

    ``0`` is also the pytest guard (tests/conftest.py forces it), so no
    thread is ever spawned under the test suite.
    """
    if interval_minutes <= 0:
        logger.info("Auto-scanner disabled (interval %d)", interval_minutes)
        return
    thread = threading.Thread(
        target=_auto_scan_loop, args=(interval_minutes,), daemon=True
    )
    logger.info("Auto-scanner started: every %d minute(s)", interval_minutes)
    thread.start()


def _auto_scan_loop(interval_minutes: int) -> None:
    """Scan all repositories every tick; a failed iteration never kills it.

    A fresh ``SessionLocal`` per iteration (never a request session), closed
    in ``finally``; the sleep happens after the close, so a mid-iteration DB
    blip only costs that tick.
    """
    while True:
        db = SessionLocal()
        try:
            reports = scan_all(db)
            total_errors = sum(report.errors for report in reports)
            logger.info(
                "Auto-scan complete: %d repo type(s), %d error(s)",
                len(reports),
                total_errors,
            )
        except Exception:
            logger.exception("Auto-scan iteration failed; retrying on the next tick")
        finally:
            db.close()
        time.sleep(interval_minutes * 60)
