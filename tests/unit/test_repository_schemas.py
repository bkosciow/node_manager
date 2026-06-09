"""Unit tests for Repository Pydantic schemas."""

import pytest

from app.schemas.repository import (
    RepositoryCreate,
    RepositoryFileResponse,
    RepositoryResponse,
)


class TestRepositoryCreate:
    def test_valid_create(self):
        """AC: RepositoryCreate accepts name and repo_type."""
        data = RepositoryCreate(name="node_north", repo_type="microplate")
        assert data.name == "node_north"
        assert data.repo_type == "microplate"

    def test_valid_userspace_type(self):
        """AC: repo_type 'userspace' is accepted."""
        data = RepositoryCreate(name="test", repo_type="userspace")
        assert data.repo_type == "userspace"

    def test_invalid_repo_type_raises(self):
        """AC: repo_type validator rejects invalid values."""
        with pytest.raises(ValueError, match="must be one of"):
            RepositoryCreate(name="test", repo_type="invalid")

    def test_empty_name_raises(self):
        """AC: name validator rejects empty strings."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            RepositoryCreate(name="", repo_type="microplate")

    def test_whitespace_name_raises(self):
        """AC: name validator rejects whitespace-only strings."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            RepositoryCreate(name="   ", repo_type="microplate")

    def test_name_is_stripped(self):
        """AC: name is stripped of whitespace."""
        data = RepositoryCreate(name="  node_north  ", repo_type="microplate")
        assert data.name == "node_north"

    def test_repo_type_is_case_insensitive(self):
        """AC: repo_type is lowercased."""
        data = RepositoryCreate(name="test", repo_type="Microplate")
        assert data.repo_type == "microplate"


class TestRepositoryFileResponse:
    def test_has_required_fields(self):
        """AC: RepositoryFileResponse has id, filename, sha256, updated_at."""
        from datetime import datetime

        data = RepositoryFileResponse(
            id=1,
            filename="core.py",
            sha256="a" * 64,
            updated_at=datetime(2026, 6, 9, 10, 0, 0),
        )
        assert data.id == 1
        assert data.filename == "core.py"
        assert data.sha256 == "a" * 64


class TestRepositoryResponse:
    def test_has_required_fields(self):
        """AC: RepositoryResponse has id, name, repo_type, files, created_at."""
        from datetime import datetime

        data = RepositoryResponse(
            id=1,
            name="node_north",
            repo_type="microplate",
            files=[
                RepositoryFileResponse(
                    id=1,
                    filename="core.py",
                    sha256="a" * 64,
                    updated_at=datetime(2026, 6, 9, 10, 0, 0),
                )
            ],
            created_at=datetime(2026, 6, 9, 10, 0, 0),
        )
        assert data.id == 1
        assert data.name == "node_north"
        assert data.repo_type == "microplate"
        assert len(data.files) == 1
        assert data.files[0].filename == "core.py"

    def test_empty_files_list(self):
        """AC: files can be an empty list."""
        from datetime import datetime

        data = RepositoryResponse(
            id=1,
            name="node_north",
            repo_type="microplate",
            files=[],
            created_at=datetime(2026, 6, 9, 10, 0, 0),
        )
        assert data.files == []
