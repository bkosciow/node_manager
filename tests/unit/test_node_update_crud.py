"""Unit tests for NodeUpdate CRUD operations."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.crud.node_update import (
    create_node_update,
    get_node_update_by_token,
    list_node_updates,
    record_fetched_file,
    record_validated_file,
)
from app.db.base import Base
from app.models.device import Device
from app.models.node_update import NodeUpdate
from app.models.repository import Repository
from app.schemas.node_update import NodeUpdateCreate

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
    repo = Repository(name="node_north", repo_type="userspace")
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def _create_session(
    db_session: Session,
    device: Device,
    repo: Repository,
    token: str = "tok-1",
    files: list[str] | None = None,
) -> NodeUpdate:
    """Create an upgrade session via the CRUD layer."""
    return create_node_update(
        db_session,
        NodeUpdateCreate(
            token=token,
            device_id=device.id,
            repository_id=repo.id,
            repo_type="userspace",
            files=files if files is not None else ["config.py", "main.py"],
        ),
    )


class TestCreateNodeUpdate:
    def test_creates_session_with_fields(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: session created with caller-supplied token and files."""
        session = _create_session(
            db_session, sample_device, sample_repo, files=["config.py"]
        )

        assert session.id is not None
        assert session.token == "tok-1"
        assert session.device_id == sample_device.id
        assert session.repository_id == sample_repo.id
        assert session.repo_type == "userspace"
        assert session.files == ["config.py"]
        assert session.fetched_files == []
        assert session.validated_files == []
        assert session.created_at is not None

    def test_duplicate_token_raises_integrity_error(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: uq_node_update_token rejects a repeated token."""
        _create_session(db_session, sample_device, sample_repo, token="dup")

        with pytest.raises(IntegrityError):
            _create_session(db_session, sample_device, sample_repo, token="dup")
        db_session.rollback()


class TestGetNodeUpdateByToken:
    def test_returns_session(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: lookup by token returns the session."""
        session = _create_session(db_session, sample_device, sample_repo)

        found = get_node_update_by_token(db_session, session.token)

        assert found is not None
        assert found.id == session.id

    def test_unknown_token_returns_none(self, db_session: Session):
        """AC: unknown token -> None."""
        assert get_node_update_by_token(db_session, "nope") is None


class TestListNodeUpdates:
    def test_newest_first(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: ordering is created_at desc."""
        older = _create_session(
            db_session, sample_device, sample_repo, token="old"
        )
        newer = _create_session(
            db_session, sample_device, sample_repo, token="new"
        )
        older.created_at = datetime(2026, 10, 1, 12, 0, 0)
        newer.created_at = datetime(2026, 10, 2, 12, 0, 0)
        db_session.commit()

        rows = list_node_updates(db_session, sample_device.id)

        assert [r.id for r in rows] == [newer.id, older.id]

    def test_id_breaks_same_second_ties(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: identical created_at -> higher id first."""
        a = _create_session(db_session, sample_device, sample_repo, token="a")
        b = _create_session(db_session, sample_device, sample_repo, token="b")
        ts = datetime(2026, 10, 1, 12, 0, 0)
        a.created_at = ts
        b.created_at = ts
        db_session.commit()

        rows = list_node_updates(db_session, sample_device.id)

        assert [r.id for r in rows] == [b.id, a.id]

    def test_excludes_other_devices(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: only the requested device's sessions are returned."""
        other = Device(chip_id="ZZZ999", node="sensor-9")
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        _create_session(db_session, other, sample_repo, token="x")

        assert list_node_updates(db_session, sample_device.id) == []


class TestRecordFetchedFile:
    def test_appends_filename(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: fetch hit appended to fetched_files."""
        session = _create_session(db_session, sample_device, sample_repo)

        recorded = record_fetched_file(db_session, session.token, "main.py")

        assert recorded is not None
        assert session.fetched_files == ["main.py"]

    def test_deduplicates(self, db_session: Session, sample_device, sample_repo):
        """AC: same filename recorded twice -> single entry."""
        session = _create_session(db_session, sample_device, sample_repo)

        record_fetched_file(db_session, session.token, "main.py")
        record_fetched_file(db_session, session.token, "main.py")

        assert session.fetched_files == ["main.py"]

    def test_unknown_token_returns_none(self, db_session: Session):
        """AC: unknown token -> None, no error."""
        assert record_fetched_file(db_session, "nope", "main.py") is None


class TestRecordValidatedFile:
    def test_appends_filename(
        self, db_session: Session, sample_device, sample_repo
    ):
        """AC: validate hit appended to validated_files."""
        session = _create_session(db_session, sample_device, sample_repo)

        recorded = record_validated_file(db_session, session.token, "main.py")

        assert recorded is not None
        assert session.validated_files == ["main.py"]

    def test_deduplicates(self, db_session: Session, sample_device, sample_repo):
        """AC: same filename validated twice -> single entry."""
        session = _create_session(db_session, sample_device, sample_repo)

        record_validated_file(db_session, session.token, "main.py")
        record_validated_file(db_session, session.token, "main.py")

        assert session.validated_files == ["main.py"]

    def test_unknown_token_returns_none(self, db_session: Session):
        """AC: unknown token -> None, no error."""
        assert record_validated_file(db_session, "nope", "main.py") is None
