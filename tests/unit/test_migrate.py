"""Unit tests for app.db.migrate.run_migrations() (SPEC-005).

run_migrations() is exercised against a throwaway SQLite file — never the
app's real engine / .env URL — so the suite stays migration-independent
(the shared test engine keeps its own create_all).
"""

import sqlite3
from pathlib import Path

from app.config import settings
from app.db.migrate import run_migrations

# tests/unit/test_migrate.py -> unit -> tests -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _has_revisions() -> bool:
    """True once revision files are committed (the baseline lands in T7)."""
    versions = _REPO_ROOT / "migrations" / "versions"
    return any(versions.glob("*.py"))


def test_run_migrations_runs_clean(tmp_path, monkeypatch):
    """In-process call completes without raising (the entrypoint contract):
    DB reachable + URL overridden from settings is all startup() relies on."""
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path}/migrate.db"
    )
    run_migrations()


def test_run_migrations_applies_baseline(tmp_path, monkeypatch):
    """A fresh SQLite gets the committed revisions applied on demand."""
    db_path = tmp_path / "migrate.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    run_migrations()

    if not _has_revisions():
        # Pre-baseline (SPEC-005 T7 not yet run): nothing to assert yet.
        return

    con = sqlite3.connect(str(db_path))
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        con.close()
    # The version ledger must exist once revisions have been applied.
    assert "alembic_version" in tables
    # Baseline schema landed on SQLite; devices is the canary table.
    assert "devices" in tables
