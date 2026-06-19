"""Unit tests for NodeRepository model and schemas."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.device import Device
from app.models.node_repository import NodeRepository
from app.models.repository import Repository
from app.schemas.node_repository import (
    RepoAssignmentCreate,
    RepoAssignmentResponse,
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
def sample_device(db_session: Session) -> Device:
    device = Device(chip_id="ABC123", node="sensor-1")
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


@pytest.fixture
def sample_repo(db_session: Session) -> Repository:
    repo = Repository(name="node_north", repo_type="microplate")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


class TestNodeRepositoryModel:
    def test_has_required_columns(self):
        """AC: NodeRepository has id, device_id, repository_id, repo_type, assigned_at."""
        mapper = NodeRepository.__table__.columns.keys()
        assert "id" in mapper
        assert "device_id" in mapper
        assert "repository_id" in mapper
        assert "repo_type" in mapper
        assert "assigned_at" in mapper

    def test_device_id_is_foreign_key(self):
        """AC: device_id is FK to devices.id with CASCADE."""
        fks = NodeRepository.__table__.foreign_keys
        fk_list = list(fks)
        assert len(fk_list) == 2
        device_fk = [fk for fk in fk_list if fk.column.table.name == "devices"]
        assert len(device_fk) == 1

    def test_repository_id_is_foreign_key(self):
        """AC: repository_id is FK to repositories.id with CASCADE."""
        fks = NodeRepository.__table__.foreign_keys
        fk_list = list(fks)
        repo_fk = [fk for fk in fk_list if fk.column.table.name == "repositories"]
        assert len(repo_fk) == 1

    def test_unique_constraint_on_device_id_and_repo_type(self):
        """AC: Composite unique constraint on (device_id, repo_type)."""
        constraints = {
            constraint.name
            for constraint in NodeRepository.__table__.constraints
            if constraint.name
        }
        assert "uq_device_repo_type" in constraints

    def test_relationship_to_device(self):
        """AC: NodeRepository.device relationship exists."""
        rel = NodeRepository.__mapper__.relationships["device"]
        assert rel.argument == "Device"

    def test_relationship_to_repository(self):
        """AC: NodeRepository.repository relationship exists."""
        rel = NodeRepository.__mapper__.relationships["repository"]
        assert rel.argument == "Repository"

    def test_create_assignment_in_db(self, db_session: Session, sample_device, sample_repo):
        """AC: NodeRepository record can be inserted and retrieved."""
        assignment = NodeRepository(
            device_id=sample_device.id,
            repository_id=sample_repo.id,
            repo_type="microplate",
        )
        db_session.add(assignment)
        db_session.commit()
        db_session.refresh(assignment)

        assert assignment.id is not None
        assert assignment.device_id == sample_device.id
        assert assignment.repository_id == sample_repo.id
        assert assignment.repo_type == "microplate"
        assert assignment.assigned_at is not None

    def test_duplicate_device_type_raises(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: Duplicate (device_id, repo_type) raises IntegrityError."""
        db_session.add(NodeRepository(
            device_id=sample_device.id,
            repository_id=sample_repo.id,
            repo_type="microplate",
        ))
        db_session.commit()

        repo2 = Repository(name="node_south", repo_type="microplate")
        db_session.add(repo2)
        db_session.commit()
        db_session.refresh(repo2)

        db_session.add(NodeRepository(
            device_id=sample_device.id,
            repository_id=repo2.id,
            repo_type="microplate",
        ))
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()


class TestRepoAssignmentCreate:
    def test_valid_create(self):
        """AC: RepoAssignmentCreate accepts repository_id."""
        data = RepoAssignmentCreate(repository_id=1)
        assert data.repository_id == 1


class TestRepoAssignmentResponse:
    def test_has_required_fields(self):
        """AC: RepoAssignmentResponse has all required fields."""
        from datetime import datetime

        data = RepoAssignmentResponse(
            id=1,
            device_id=1,
            repository_id=1,
            repo_type="microplate",
            assigned_at=datetime(2026, 6, 9, 10, 0, 0),
        )
        assert data.id == 1
        assert data.device_id == 1
        assert data.repository_id == 1
        assert data.repo_type == "microplate"
