"""Unit tests for NodeRepository CRUD operations."""

import pytest
from sqlalchemy.orm import Session

from app.crud.node_repository import assign_repo_to_node, get_assignments
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.device import Device
from app.models.node_repository import NodeRepository
from app.models.repository import Repository


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Session:
    session = SessionLocal()
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


class TestAssignRepoToNode:
    def test_create_new_assignment(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: assign_repo_to_node creates assignment."""
        result = assign_repo_to_node(
            db_session, sample_device.id, sample_repo.id, "microplate"
        )

        assert result is not None
        assert result.device_id == sample_device.id
        assert result.repository_id == sample_repo.id
        assert result.repo_type == "microplate"

    def test_replace_existing_assignment(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: assigning same type replaces old assignment."""
        repo2 = Repository(name="node_south", repo_type="microplate")
        db_session.add(repo2)
        db_session.commit()
        db_session.refresh(repo2)

        assign_repo_to_node(
            db_session, sample_device.id, sample_repo.id, "microplate"
        )
        result = assign_repo_to_node(
            db_session, sample_device.id, repo2.id, "microplate"
        )

        assert result is not None
        assert result.repository_id == repo2.id

        assignments = get_assignments(db_session, sample_device.id)
        assert len(assignments) == 1

    def test_assign_second_type_to_same_node(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: assigning different type creates second assignment."""
        userspace_repo = Repository(
            name="userspace_v1", repo_type="userspace"
        )
        db_session.add(userspace_repo)
        db_session.commit()
        db_session.refresh(userspace_repo)

        assign_repo_to_node(
            db_session, sample_device.id, sample_repo.id, "microplate"
        )
        result = assign_repo_to_node(
            db_session, sample_device.id, userspace_repo.id, "userspace"
        )

        assert result is not None
        assignments = get_assignments(db_session, sample_device.id)
        assert len(assignments) == 2

    def test_nonexistent_device_returns_none(
        self, db_session: Session, sample_repo
    ):
        """AC: assign_repo_to_node returns None for missing device."""
        result = assign_repo_to_node(
            db_session, 9999, sample_repo.id, "microplate"
        )
        assert result is None

    def test_nonexistent_repo_returns_none(
        self, db_session: Session, sample_device
    ):
        """AC: assign_repo_to_node returns None for missing repo."""
        result = assign_repo_to_node(
            db_session, sample_device.id, 9999, "microplate"
        )
        assert result is None


class TestGetAssignments:
    def test_get_all_assignments(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: get_assignments returns all assignments for device."""
        assign_repo_to_node(
            db_session, sample_device.id, sample_repo.id, "microplate"
        )

        assignments = get_assignments(db_session, sample_device.id)
        assert len(assignments) == 1
        assert assignments[0].repository_id == sample_repo.id

    def test_get_empty_assignments(
        self, db_session: Session, sample_device
    ):
        """AC: get_assignments returns empty list when no assignments."""
        assignments = get_assignments(db_session, sample_device.id)
        assert assignments == []
