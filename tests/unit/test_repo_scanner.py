"""Unit tests for repository scanner logic."""

import hashlib

from repo_scanner import compute_sha256, discover_repos


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
