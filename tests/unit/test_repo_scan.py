"""Unit tests for the shared scan core in app/services/repo_scan.py."""

import hashlib
import logging
import threading

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.crud.repository import create_repository, upsert_repository_file
from app.db.base import Base
from app.models.repository import Repository, RepositoryFile
from app.schemas.repository import RepositoryCreate
from app.services import repo_scan
from app.services.repo_scan import (
    list_repo_files_on_disk,
    scan_all,
    scan_repo,
    start_auto_scan,
)

# In-memory SQLite — isolated from any production database.
_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db_session() -> Session:
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tmp_upgrades(tmp_path, monkeypatch):
    """Point settings.upgrades_dir at an empty temp directory."""
    upgrades_dir = tmp_path / "upgrades"
    upgrades_dir.mkdir()
    monkeypatch.setattr(settings, "upgrades_dir", str(upgrades_dir))
    return upgrades_dir


def _write_file(upgrades_dir, repo_name: str, repo_type: str, filename: str) -> None:
    type_dir = upgrades_dir / repo_name / f"_{repo_type}"
    type_dir.mkdir(parents=True, exist_ok=True)
    (type_dir / filename).write_text(filename)


def _seed_repo(db: Session, name: str = "node_north", repo_type: str = "userspace"):
    repo = create_repository(db, RepositoryCreate(name=name, repo_type=repo_type))
    db.commit()
    return repo


class TestScanRepo:
    """Report counting, no-wipe guard, and per-file error semantics."""

    def test_new_files_are_added(self, db_session, tmp_upgrades):
        """AC: first scan of a repo adds a row per on-disk file."""
        _write_file(tmp_upgrades, "node_north", "userspace", "main.py")
        _write_file(tmp_upgrades, "node_north", "userspace", "util.py")

        report = scan_repo(db_session, "node_north", "userspace", ["main.py", "util.py"])

        assert report.files_found == 2
        assert report.files_added == 2
        assert report.files_updated == 0
        assert report.files_unchanged == 0
        assert report.files_removed == 0
        assert report.errors == 0
        # repository row auto-created
        assert (
            db_session.execute(
                select(func.count()).select_from(Repository)
            ).scalar()
            == 1
        )

    def test_repeated_scan_counts_unchanged(self, db_session, tmp_upgrades):
        """AC: rescan with no disk changes classifies every file unchanged."""
        _write_file(tmp_upgrades, "node_north", "userspace", "main.py")
        scan_repo(db_session, "node_north", "userspace", ["main.py"])

        report = scan_repo(db_session, "node_north", "userspace", ["main.py"])

        assert report.files_added == 0
        assert report.files_unchanged == 1

    def test_changed_file_counts_as_updated(self, db_session, tmp_upgrades):
        """AC: modified content -> updated count, row hash refreshed."""
        _write_file(tmp_upgrades, "node_north", "userspace", "main.py")
        _write_file(tmp_upgrades, "node_north", "userspace", "util.py")
        scan_repo(db_session, "node_north", "userspace", ["main.py", "util.py"])

        file_path = tmp_upgrades / "node_north" / "_userspace" / "main.py"
        file_path.write_text("changed content")
        expected = hashlib.sha256(b"changed content").hexdigest()

        report = scan_repo(db_session, "node_north", "userspace", ["main.py", "util.py"])

        assert report.files_updated == 1
        assert report.files_unchanged == 1
        stored = (
            db_session.execute(
                select(RepositoryFile).where(RepositoryFile.filename == "main.py")
            )
            .scalars()
            .one()
        )
        assert stored.sha256 == expected

    def test_deleted_file_is_removed(self, db_session, tmp_upgrades):
        """AC: file missing from the scan list has its row deleted."""
        _write_file(tmp_upgrades, "node_north", "userspace", "main.py")
        _write_file(tmp_upgrades, "node_north", "userspace", "util.py")
        scan_repo(db_session, "node_north", "userspace", ["main.py", "util.py"])

        report = scan_repo(db_session, "node_north", "userspace", ["main.py"])

        assert report.files_removed == 1
        remaining = db_session.execute(select(RepositoryFile)).scalars().all()
        assert [f.filename for f in remaining] == ["main.py"]

    def test_empty_file_list_is_no_wipe(self, db_session, tmp_upgrades):
        """AC: empty list -> no upserts, no cleanup, records survive."""
        _seed_repo(db_session)
        _write_file(tmp_upgrades, "node_north", "userspace", "main.py")
        _write_file(tmp_upgrades, "node_north", "userspace", "util.py")
        scan_repo(db_session, "node_north", "userspace", ["main.py", "util.py"])
        assert (
            db_session.execute(
                select(func.count()).select_from(RepositoryFile)
            ).scalar()
            == 2
        )

        report = scan_repo(db_session, "node_north", "userspace", [])

        assert report.files_found == 0
        assert report.files_removed == 0
        assert (
            db_session.execute(
                select(func.count()).select_from(RepositoryFile)
            ).scalar()
            == 2
        )

    def test_unreadable_file_is_error_and_row_removed(
        self, caplog, db_session, tmp_upgrades, monkeypatch
    ):
        """AC: unreadable file -> errors count, row deleted, scan continues."""
        repo = _seed_repo(db_session)
        _write_file(tmp_upgrades, "node_north", "userspace", "main.py")
        _write_file(tmp_upgrades, "node_north", "userspace", "bad.py")
        upsert_repository_file(db_session, repo.id, "main.py", "m" * 64)
        upsert_repository_file(db_session, repo.id, "bad.py", "b" * 64)
        db_session.commit()

        real_compute = repo_scan.compute_sha256

        def flaky_compute(filepath: str) -> str:
            if filepath.endswith("bad.py"):
                raise OSError("simulated read failure")
            return real_compute(filepath)

        monkeypatch.setattr(repo_scan, "compute_sha256", flaky_compute)
        caplog.set_level(logging.ERROR)

        report = scan_repo(
            db_session, "node_north", "userspace", ["main.py", "bad.py"]
        )

        assert report.errors == 1
        assert report.files_updated == 1  # main.py's placeholder hash refreshed
        assert report.files_removed == 1  # bad.py's row was wiped
        remaining = {
            f.filename
            for f in db_session.execute(select(RepositoryFile)).scalars().all()
        }
        assert remaining == {"main.py"}
        assert any("Error reading file" in r.message for r in caplog.records)


class TestListRepoFilesOnDisk:
    def test_missing_directory_returns_empty(self, tmp_upgrades):
        """AC: no type dir on disk -> [] (feeds the endpoint's 404 path)."""
        assert list_repo_files_on_disk("ghost", "userspace") == []

    def test_empty_directory_returns_empty(self, tmp_upgrades):
        """AC: dir exists but has no files -> []."""
        (tmp_upgrades / "node_north" / "_userspace").mkdir(parents=True)
        assert list_repo_files_on_disk("node_north", "userspace") == []

    def test_lists_files_and_ignores_subdirectories(self, tmp_upgrades):
        """AC: only regular files are listed, subdirectories are skipped."""
        _write_file(tmp_upgrades, "node_north", "userspace", "main.py")
        subdir = tmp_upgrades / "node_north" / "_userspace" / "nested"
        subdir.mkdir()
        (subdir / "deep.py").write_text("deep")

        assert list_repo_files_on_disk("node_north", "userspace") == ["main.py"]


class TestScanAll:
    def test_scans_every_discovered_repo_type(self, db_session, tmp_upgrades):
        """AC: one report per discovered repo type."""
        _write_file(tmp_upgrades, "node_north", "userspace", "main.py")
        _write_file(tmp_upgrades, "node_south", "microplate", "core.py")

        reports = scan_all(db_session)

        assert [(r.repo_name, r.repo_type) for r in reports] == [
            ("node_north", "userspace"),
            ("node_south", "microplate"),
        ]
        assert all(r.files_found == 1 for r in reports)

    def test_missing_upgrades_dir_returns_empty(self, db_session, monkeypatch):
        """AC: whole upgrades dir absent -> no reports, no DB writes."""
        monkeypatch.setattr(settings, "upgrades_dir", "/nonexistent-upgrades-dir")
        assert scan_all(db_session) == []
        assert (
            db_session.execute(
                select(func.count()).select_from(Repository)
            ).scalar()
            == 0
        )


class _SleepGate:
    """Fake time.sleep: records calls, raises SystemExit after ``stop_at``."""

    def __init__(self, stop_at: int = 1):
        self.calls: list[float] = []
        self.stop_at = stop_at

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if len(self.calls) >= self.stop_at:
            raise SystemExit


class TestStartAutoScan:
    """Thread spawn and the disable guard."""

    def test_disabled_for_zero_interval(self, caplog):
        """AC: interval 0 -> one log line, no thread spawned."""
        caplog.set_level(logging.INFO)
        start_auto_scan(0)
        assert "Auto-scanner disabled (interval 0)" in caplog.text

    def test_disabled_for_negative_interval(self, caplog):
        """AC: negative interval disables the loop as well."""
        caplog.set_level(logging.INFO)
        start_auto_scan(-5)
        assert "Auto-scanner disabled (interval -5)" in caplog.text

    def test_spawns_daemon_thread_with_interval(self, monkeypatch):
        """AC: positive interval -> thread running the loop with that interval."""
        started = threading.Event()
        intervals: list[int] = []

        def fake_loop(interval_minutes: int) -> None:
            intervals.append(interval_minutes)
            started.set()

        monkeypatch.setattr(repo_scan, "_auto_scan_loop", fake_loop)
        start_auto_scan(5)
        assert started.wait(5.0)
        assert intervals == [5]


class TestAutoScanLoop:
    """_auto_scan_loop called directly, with SessionLocal and time.sleep patched."""

    @pytest.fixture
    def loop_env(self, monkeypatch):
        """Fresh sessionmaker for the loop (the app's would hit the real DB)."""
        loop_session_local = sessionmaker(
            autocommit=False, autoflush=False, bind=_engine
        )
        monkeypatch.setattr(repo_scan, "SessionLocal", loop_session_local)
        return loop_session_local

    def test_successful_tick_logs_summary_and_sleeps_interval(
        self, db_session, loop_env, monkeypatch, caplog
    ):
        """AC: scan_all runs, summary logged, sleep(interval * 60) after close."""
        gate = _SleepGate(stop_at=1)
        monkeypatch.setattr(repo_scan, "scan_all", lambda db: [])
        monkeypatch.setattr(repo_scan.time, "sleep", gate)
        caplog.set_level(logging.INFO)

        with pytest.raises(SystemExit):
            repo_scan._auto_scan_loop(10)

        assert gate.calls == [600]
        assert "Auto-scan complete: 0 repo type(s), 0 error(s)" in caplog.text

    def test_failed_iteration_is_retried_next_tick(
        self, db_session, loop_env, monkeypatch, caplog
    ):
        """AC: a failed scan never kills the loop; the next tick re-runs it."""
        calls = {"count": 0}

        def flaky_scan_all(db) -> list:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("transient DB outage")
            return []

        gate = _SleepGate(stop_at=2)
        monkeypatch.setattr(repo_scan, "scan_all", flaky_scan_all)
        monkeypatch.setattr(repo_scan.time, "sleep", gate)
        caplog.set_level(logging.ERROR)

        with pytest.raises(SystemExit):
            repo_scan._auto_scan_loop(1)

        assert calls["count"] == 2  # failed tick retried on the second one
        assert gate.calls == [60, 60]
        failed = [
            r for r in caplog.records if "Auto-scan iteration failed" in r.message
        ]
        assert len(failed) == 1
        assert failed[0].levelno == logging.ERROR
