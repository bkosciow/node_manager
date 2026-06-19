"""Unit tests for Repository CRUD operations."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.crud.repository import (
    cleanup_repository_files,
    create_repository,
    get_repository,
    get_repositories,
    upsert_repository_file,
)
from app.db.base import Base
from app.models.repository import RepositoryFile
from app.schemas.repository import RepositoryCreate

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


class TestCreateRepository:
    def test_create_repository(self, db_session: Session):
        """AC: create_repository inserts and returns with id."""
        data = RepositoryCreate(name="node_north", repo_type="microplate")
        repo = create_repository(db_session, data)

        assert repo.id is not None
        assert repo.name == "node_north"
        assert repo.repo_type == "microplate"
        assert repo.created_at is not None


class TestGetRepository:
    def test_get_existing_repository(self, db_session: Session):
        """AC: get_repository returns repository by id."""
        data = RepositoryCreate(name="node_north", repo_type="microplate")
        repo = create_repository(db_session, data)

        found = get_repository(db_session, repo.id)
        assert found is not None
        assert found.id == repo.id
        assert found.name == "node_north"

    def test_get_missing_repository(self, db_session: Session):
        """AC: get_repository returns None for missing id."""
        found = get_repository(db_session, 9999)
        assert found is None

    def test_get_repository_eager_loads_files(self, db_session: Session):
        """AC: get_repository eager-loads files relationship."""
        data = RepositoryCreate(name="node_north", repo_type="microplate")
        repo = create_repository(db_session, data)
        file_obj = RepositoryFile(
            repository_id=repo.id,
            filename="core.py",
            sha256="a" * 64,
        )
        db_session.add(file_obj)
        db_session.commit()

        found = get_repository(db_session, repo.id)
        assert found is not None
        assert len(found.files) == 1
        assert found.files[0].filename == "core.py"


class TestGetRepositories:
    def test_get_repositories_by_type(self, db_session: Session):
        """AC: get_repositories filters by repo_type."""
        create_repository(
            db_session, RepositoryCreate(name="north", repo_type="microplate")
        )
        create_repository(
            db_session, RepositoryCreate(name="south", repo_type="userspace")
        )

        results = get_repositories(db_session, "microplate")
        assert len(results) == 1
        assert results[0].name == "north"

    def test_get_repositories_empty(self, db_session: Session):
        """AC: get_repositories returns empty list when no match."""
        results = get_repositories(db_session, "microplate")
        assert results == []


class TestUpsertRepositoryFile:
    def test_insert_new_file(self, db_session: Session):
        """AC: upsert_repository_file inserts new file."""
        data = RepositoryCreate(name="node_north", repo_type="microplate")
        repo = create_repository(db_session, data)

        file_obj = upsert_repository_file(db_session, repo.id, "core.py", "a" * 64)

        assert file_obj.id is not None
        assert file_obj.filename == "core.py"
        assert file_obj.sha256 == "a" * 64

    def test_update_existing_file(self, db_session: Session):
        """AC: upsert_repository_file updates sha256 for existing file."""
        data = RepositoryCreate(name="node_north", repo_type="microplate")
        repo = create_repository(db_session, data)

        file_obj = upsert_repository_file(db_session, repo.id, "core.py", "a" * 64)
        old_id = file_obj.id

        updated = upsert_repository_file(db_session, repo.id, "core.py", "b" * 64)

        assert updated.id == old_id
        assert updated.sha256 == "b" * 64


class TestCleanupRepositoryFiles:
    def test_cleanup_removes_deleted_files(self, db_session: Session):
        """AC: cleanup removes files not in existing_filenames set."""
        data = RepositoryCreate(name="node_north", repo_type="microplate")
        repo = create_repository(db_session, data)

        upsert_repository_file(db_session, repo.id, "core.py", "a" * 64)
        upsert_repository_file(db_session, repo.id, "old.py", "b" * 64)

        deleted = cleanup_repository_files(
            db_session, repo.id, {"core.py"}
        )

        assert deleted == 1
        remaining = db_session.query(RepositoryFile).filter_by(
            repository_id=repo.id
        ).all()
        assert len(remaining) == 1
        assert remaining[0].filename == "core.py"

    def test_cleanup_nothing_to_remove(self, db_session: Session):
        """AC: cleanup returns 0 when all files exist."""
        data = RepositoryCreate(name="node_north", repo_type="microplate")
        repo = create_repository(db_session, data)

        upsert_repository_file(db_session, repo.id, "core.py", "a" * 64)

        deleted = cleanup_repository_files(
            db_session, repo.id, {"core.py"}
        )

        assert deleted == 0
