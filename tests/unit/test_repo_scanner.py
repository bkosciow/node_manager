"""Unit tests for the shared repository scanner core (repo_scan service)."""

import hashlib
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.base import Base
from app.models.repository import Repository, RepositoryFile
from app.services.repo_scan import compute_sha256, discover_repos, scan_repo


@pytest.fixture
def db_session():
    """In-memory SQLite session for DB integration tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def upgrades_dir_with_repo(tmp_path):
    """Create a temp directory with a mock repo structure."""
    repo_dir = tmp_path / "node_north" / "_microplate"
    repo_dir.mkdir(parents=True)
    (repo_dir / "core.py").write_text("print('hello')")
    (repo_dir / "utils.py").write_text("def util(): pass")
    return tmp_path


class TestComputeSha256:
    def test_correct_hash_for_known_content(self, tmp_path):
        """AC: scanner computes correct SHA256 for a file."""
        content = b"hello world"
        filepath = tmp_path / "test.txt"
        filepath.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        assert compute_sha256(str(filepath)) == expected

    def test_hash_for_empty_file(self, tmp_path):
        """AC: scanner handles empty files."""
        filepath = tmp_path / "empty.txt"
        filepath.write_bytes(b"")

        expected = hashlib.sha256(b"").hexdigest()
        assert compute_sha256(str(filepath)) == expected


class TestDiscoverRepos:
    def test_identifies_microplate_repo(self, tmp_path):
        """AC: scanner identifies repos with _microplate subfolder."""
        repo_dir = tmp_path / "node_north" / "_microplate"
        repo_dir.mkdir(parents=True)
        (repo_dir / "core.py").write_text("print('hello')")

        result = discover_repos(str(tmp_path))
        assert "node_north" in result
        assert "microplate" in result["node_north"]
        assert "core.py" in result["node_north"]["microplate"]

    def test_identifies_userspace_repo(self, tmp_path):
        """AC: scanner identifies repos with _userspace subfolder."""
        repo_dir = tmp_path / "node_south" / "_userspace"
        repo_dir.mkdir(parents=True)
        (repo_dir / "main.py").write_text("main()")

        result = discover_repos(str(tmp_path))
        assert "node_south" in result
        assert "userspace" in result["node_south"]

    def test_identifies_both_types(self, tmp_path):
        """AC: scanner identifies both types in same repo."""
        for type_dir in ("_microplate", "_userspace"):
            dir_path = tmp_path / "node_north" / type_dir
            dir_path.mkdir(parents=True)
            (dir_path / "file.py").write_text("code")

        result = discover_repos(str(tmp_path))
        assert "microplate" in result["node_north"]
        assert "userspace" in result["node_north"]

    def test_ignores_non_repo_folders(self, tmp_path):
        """AC: scanner ignores folders that are not _microplate or _userspace."""
        repo_dir = tmp_path / "node_north" / "_microplate"
        repo_dir.mkdir(parents=True)
        (repo_dir / "core.py").write_text("code")

        other_dir = tmp_path / "node_north" / "_other"
        other_dir.mkdir(parents=True)
        (other_dir / "file.py").write_text("code")

        result = discover_repos(str(tmp_path))
        assert "node_north" in result
        assert "microplate" in result["node_north"]
        assert "other" not in result.get("node_north", {})

    def test_ignores_files_in_repo_root(self, tmp_path):
        """AC: scanner ignores files in repo root (only dirs matter)."""
        repo_dir = tmp_path / "node_north"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("readme")
        micro_dir = repo_dir / "_microplate"
        micro_dir.mkdir(parents=True)
        (micro_dir / "core.py").write_text("code")

        result = discover_repos(str(tmp_path))
        assert "node_north" in result
        assert "README.md" not in result["node_north"].get("microplate", [])
        assert "core.py" in result["node_north"]["microplate"]

    def test_returns_empty_for_missing_directory(self):
        """AC: scanner handles missing /upgrades directory gracefully."""
        result = discover_repos("/nonexistent/path")
        assert result == {}

    def test_returns_empty_for_empty_directory(self, tmp_path):
        """AC: scanner returns empty dict for empty directory."""
        result = discover_repos(str(tmp_path))
        assert result == {}

    def test_ignores_subdirectories_in_type_folder(self, tmp_path):
        """AC: scanner ignores subdirectories inside type folder (files only)."""
        repo_dir = tmp_path / "node_north" / "_microplate"
        repo_dir.mkdir(parents=True)
        (repo_dir / "core.py").write_text("code")
        (repo_dir / "subdir").mkdir()
        (repo_dir / "subdir" / "nested.py").write_text("nested")

        result = discover_repos(str(tmp_path))
        assert result["node_north"]["microplate"] == ["core.py"]


class TestScanRepo:
    def test_creates_repository_for_new_repo(
        self, db_session, upgrades_dir_with_repo, monkeypatch
    ):
        """AC: scanner creates Repository record for new repo."""
        monkeypatch.setattr(settings, "upgrades_dir", str(upgrades_dir_with_repo))

        scan_repo(
            db_session, "node_north", "microplate", ["core.py", "utils.py"]
        )

        repos = db_session.query(Repository).all()
        assert len(repos) == 1
        assert repos[0].name == "node_north"
        assert repos[0].repo_type == "microplate"

    def test_upserts_new_files(self, db_session, upgrades_dir_with_repo,
                               monkeypatch):
        """AC: scanner upserts RepositoryFile records (new)."""
        monkeypatch.setattr(settings, "upgrades_dir", str(upgrades_dir_with_repo))

        scan_repo(
            db_session, "node_north", "microplate", ["core.py", "utils.py"]
        )

        repo = db_session.query(Repository).first()
        files = db_session.query(RepositoryFile).filter(
            RepositoryFile.repository_id == repo.id
        ).all()
        assert len(files) == 2
        filenames = {f.filename for f in files}
        assert "core.py" in filenames
        assert "utils.py" in filenames
        for f in files:
            assert len(f.sha256) == 64  # valid SHA256 hex

    def test_upserts_updated_files(self, db_session, upgrades_dir_with_repo,
                                   monkeypatch):
        """AC: scanner upserts RepositoryFile records (updated hash)."""
        monkeypatch.setattr(settings, "upgrades_dir", str(upgrades_dir_with_repo))

        scan_repo(
            db_session, "node_north", "microplate", ["core.py", "utils.py"]
        )

        original_hash = (
            db_session.query(RepositoryFile)
            .filter(RepositoryFile.filename == "core.py")
            .first()
            .sha256
        )

        # Modify the file content
        (upgrades_dir_with_repo / "node_north" / "_microplate" / "core.py"
         ).write_text("print('world')")

        scan_repo(
            db_session, "node_north", "microplate", ["core.py", "utils.py"]
        )

        updated_hash = (
            db_session.query(RepositoryFile)
            .filter(RepositoryFile.filename == "core.py")
            .first()
            .sha256
        )
        assert updated_hash != original_hash
        # Still only 2 files
        assert db_session.query(RepositoryFile).count() == 2

    def test_removes_deleted_file_records(
        self, db_session, upgrades_dir_with_repo, monkeypatch
    ):
        """AC: scanner removes RepositoryFile records for deleted files."""
        monkeypatch.setattr(settings, "upgrades_dir", str(upgrades_dir_with_repo))

        scan_repo(
            db_session, "node_north", "microplate", ["core.py", "utils.py"]
        )
        assert db_session.query(RepositoryFile).count() == 2

        # Simulate file deletion - only core.py remains
        scan_repo(
            db_session, "node_north", "microplate", ["core.py"]
        )

        remaining = db_session.query(RepositoryFile).all()
        assert len(remaining) == 1
        assert remaining[0].filename == "core.py"

    def test_handles_unreadable_file(self, caplog, db_session,
                                     upgrades_dir_with_repo, monkeypatch):
        """AC: scanner handles unreadable file (logs error, continues)."""
        monkeypatch.setattr(settings, "upgrades_dir", str(upgrades_dir_with_repo))

        # Make utils.py unreadable
        utils_path = upgrades_dir_with_repo / "node_north" / "_microplate" \
            / "utils.py"
        os.chmod(utils_path, 0o000)

        import logging
        caplog.set_level(logging.ERROR)

        scan_repo(
            db_session, "node_north", "microplate", ["core.py", "utils.py"]
        )

        # core.py should be synced, utils.py should fail gracefully
        repo = db_session.query(Repository).first()
        files = db_session.query(RepositoryFile).filter(
            RepositoryFile.repository_id == repo.id
        ).all()
        # Only core.py should be present (utils.py failed)
        filenames = {f.filename for f in files}
        assert "core.py" in filenames
        assert "utils.py" not in filenames
        assert any("Error reading file" in r.message for r in caplog.records)

        # Restore permissions for cleanup
        os.chmod(utils_path, 0o644)
