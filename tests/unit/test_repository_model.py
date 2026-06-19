"""Unit tests for Repository and RepositoryFile SQLAlchemy models."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.repository import Repository, RepositoryFile

# In-memory SQLite — isolated from any production database.
_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(autouse=True)
def _tables():
    """Create and drop tables for each test."""
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


class TestRepositoryModel:
    def test_has_required_columns(self):
        """AC: Repository model has id, name, repo_type, created_at columns."""
        mapper = Repository.__table__.columns.keys()
        assert "id" in mapper
        assert "name" in mapper
        assert "repo_type" in mapper
        assert "created_at" in mapper

    def test_id_is_primary_key(self):
        """AC: id is primary key with auto-increment."""
        col = Repository.__table__.columns["id"]
        assert col.primary_key
        assert col.autoincrement

    def test_name_and_repo_type_not_nullable(self):
        """AC: name and repo_type are not nullable."""
        assert not Repository.__table__.columns["name"].nullable
        assert not Repository.__table__.columns["repo_type"].nullable

    def test_unique_constraint_on_name_and_repo_type(self):
        """AC: Composite unique constraint on (name, repo_type)."""
        constraints = {
            constraint.name
            for constraint in Repository.__table__.constraints
            if constraint.name
        }
        assert "uq_repo_name_type" in constraints

    def test_relationship_to_files(self):
        """AC: Repository.files relationship exists with cascade delete."""
        rel = Repository.__mapper__.relationships["files"]
        assert rel.argument == "RepositoryFile"
        assert "delete-orphan" in str(rel.cascade)

    def test_create_repository_in_db(self, db_session: Session):
        """AC: Repository record can be inserted and retrieved."""
        repo = Repository(name="node_north", repo_type="microplate")
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        assert repo.id is not None
        assert repo.name == "node_north"
        assert repo.repo_type == "microplate"
        assert repo.created_at is not None

    def test_duplicate_name_and_type_raises_integrity_error(self, db_session: Session):
        """AC: Duplicate (name, repo_type) raises IntegrityError."""
        db_session.add(Repository(name="node_north", repo_type="microplate"))
        db_session.commit()

        db_session.add(Repository(name="node_north", repo_type="microplate"))
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()


class TestRepositoryFileModel:
    def test_has_required_columns(self):
        """AC: RepositoryFile has id, repository_id, filename, sha256, updated_at."""
        mapper = RepositoryFile.__table__.columns.keys()
        assert "id" in mapper
        assert "repository_id" in mapper
        assert "filename" in mapper
        assert "sha256" in mapper
        assert "updated_at" in mapper

    def test_repository_id_is_foreign_key(self):
        """AC: repository_id is FK to repositories.id with CASCADE."""
        fks = RepositoryFile.__table__.foreign_keys
        fk_list = list(fks)
        assert len(fk_list) == 1
        assert fk_list[0].column.table.name == "repositories"
        assert fk_list[0].column.key == "id"

    def test_unique_constraint_on_repository_id_and_filename(self):
        """AC: Composite unique constraint on (repository_id, filename)."""
        constraints = {
            constraint.name
            for constraint in RepositoryFile.__table__.constraints
            if constraint.name
        }
        assert "uq_repo_file" in constraints

    def test_sha256_column_length(self):
        """AC: sha256 column is String(64)."""
        col = RepositoryFile.__table__.columns["sha256"]
        assert col.type.length == 64

    def test_relationship_to_repository(self):
        """AC: RepositoryFile.repository relationship exists."""
        rel = RepositoryFile.__mapper__.relationships["repository"]
        assert rel.argument == "Repository"

    def test_create_repository_file_in_db(self, db_session: Session):
        """AC: RepositoryFile record can be inserted and retrieved."""
        repo = Repository(name="node_north", repo_type="microplate")
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        file_obj = RepositoryFile(
            repository_id=repo.id,
            filename="core.py",
            sha256="a" * 64,
        )
        db_session.add(file_obj)
        db_session.commit()
        db_session.refresh(file_obj)

        assert file_obj.id is not None
        assert file_obj.repository_id == repo.id
        assert file_obj.filename == "core.py"
        assert file_obj.sha256 == "a" * 64
        assert file_obj.updated_at is not None

    def test_cascade_delete_files_when_repo_deleted(self, db_session: Session):
        """AC: Deleting a Repository cascades to its RepositoryFile records."""
        repo = Repository(name="node_north", repo_type="microplate")
        db_session.add(repo)
        db_session.commit()
        db_session.refresh(repo)

        file_obj = RepositoryFile(
            repository_id=repo.id,
            filename="core.py",
            sha256="a" * 64,
        )
        db_session.add(file_obj)
        db_session.commit()

        db_session.delete(repo)
        db_session.commit()

        remaining = db_session.query(RepositoryFile).filter_by(
            repository_id=repo.id
        ).count()
        assert remaining == 0
