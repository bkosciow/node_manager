"""Unit tests for update-status (hash comparison) logic."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.crud.device import create_device
from app.crud.device_event import upsert_event
from app.crud.node_repository import assign_repo_to_node
from app.crud.repository import (
    create_repository,
    upsert_repository_file,
)
from app.crud.update_status import (
    check_update_available,
    get_device_updates,
    get_repo_file_diff,
)
from app.db.base import Base

# Register all models so tables are created.
from app.models.device import Device  # noqa: F401
from app.models.device_event import DeviceEvent  # noqa: F401
from app.models.node_repository import NodeRepository  # noqa: F401
from app.models.repository import Repository, RepositoryFile  # noqa: F401

from app.schemas.device import DeviceCreate
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _setup_device_with_repo_and_event(
    db: Session,
    repo_type: str = "microplate",
    device_hashes: dict | None = None,
    repo_files: dict | None = None,
):
    """Create device + repo + assignment + event + repo files in one shot.

    Returns ``(device, repo)``.
    """
    device = create_device(db, DeviceCreate(chip_id="DEV01", node="n1"))
    repo = create_repository(
        db, RepositoryCreate(name=f"repo_{repo_type}", repo_type=repo_type)
    )
    assign_repo_to_node(db, device.id, repo.id, repo_type)

    if device_hashes is not None:
        upsert_event(
            db, device.id, f"system.{repo_type}.hash", device_hashes
        )

    if repo_files is not None:
        for filename, sha in repo_files.items():
            upsert_repository_file(db, repo.id, filename, sha)

    return device, repo


# ---------------------------------------------------------------------------
# check_update_available
# ---------------------------------------------------------------------------


class TestCheckUpdateAvailable:
    def test_no_update_when_hashes_match(self, db_session: Session):
        files = {"core.bin": _HASH_A, "boot.bin": _HASH_B}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=files,
            repo_files=files,
        )
        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is False

    def test_update_when_one_hash_differs(self, db_session: Session):
        device_hashes = {"core.bin": _HASH_A, "boot.bin": _HASH_B}
        repo_files = {"core.bin": _HASH_A, "boot.bin": "c" * 64}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )
        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is True

    def test_update_when_file_missing_on_device(self, db_session: Session):
        device_hashes = {"core.bin": _HASH_A}
        repo_files = {"core.bin": _HASH_A, "boot.bin": _HASH_B}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )
        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is True

    def test_no_update_when_file_extra_on_device(self, db_session: Session):
        """Device-only files never set the flag (repo-driven comparison)."""
        device_hashes = {"core.bin": _HASH_A, "extra.bin": _HASH_B}
        repo_files = {"core.bin": _HASH_A}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )
        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is False

    def test_update_when_extra_and_missing_files(self, db_session: Session):
        """A missing repo file sets the flag even with device-only extras."""
        device_hashes = {"core.bin": _HASH_A, "extra.bin": _HASH_B}
        repo_files = {"core.bin": _HASH_A, "boot.bin": _HASH_B}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )
        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is True

    def test_no_update_when_repo_empty_device_has_files(
        self, db_session: Session
    ):
        """An empty repo has nothing to push -> no update."""
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes={"extra.bin": _HASH_B},
            repo_files={},
        )
        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is False

    def test_no_update_when_no_event_from_device(self, db_session: Session):
        _, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=None,  # no event
            repo_files={"core.bin": _HASH_A},
        )
        device = db_session.query(Device).filter_by(chip_id="DEV01").first()
        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is False

    def test_no_update_with_empty_sets(self, db_session: Session):
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes={},
            repo_files={},
        )
        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is False

    def test_userspace_repo_type(self, db_session: Session):
        files = {"app.bin": _HASH_A}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            repo_type="userspace",
            device_hashes=files,
            repo_files=files,
        )
        assert check_update_available(
            db_session, device.id, repo.id, "userspace"
        ) is False


# ---------------------------------------------------------------------------
# get_device_updates
# ---------------------------------------------------------------------------


class TestGetDeviceUpdates:
    def test_no_assignments_returns_false(self, db_session: Session):
        device = create_device(db_session, DeviceCreate(chip_id="D1", node="n1"))
        result = get_device_updates(db_session, device.id)
        assert result == {"microplate": False, "userspace": False}

    def test_both_up_to_date(self, db_session: Session):
        files = {"core.bin": _HASH_A}
        device = create_device(db_session, DeviceCreate(chip_id="B1", node="n1"))

        mp_repo = create_repository(
            db_session, RepositoryCreate(name="mp", repo_type="microplate")
        )
        assign_repo_to_node(db_session, device.id, mp_repo.id, "microplate")
        upsert_event(db_session, device.id, "system.microplate.hash", files)
        upsert_repository_file(db_session, mp_repo.id, "core.bin", _HASH_A)

        us_repo = create_repository(
            db_session, RepositoryCreate(name="us", repo_type="userspace")
        )
        assign_repo_to_node(db_session, device.id, us_repo.id, "userspace")
        upsert_event(db_session, device.id, "system.userspace.hash", files)
        upsert_repository_file(db_session, us_repo.id, "core.bin", _HASH_A)

        result = get_device_updates(db_session, device.id)
        assert result == {"microplate": False, "userspace": False}

    def test_one_assigned_one_not(self, db_session: Session):
        files = {"core.bin": _HASH_A}
        device = create_device(db_session, DeviceCreate(chip_id="U1", node="n1"))
        repo = create_repository(
            db_session,
            RepositoryCreate(name="micro_v1", repo_type="microplate"),
        )
        assign_repo_to_node(db_session, device.id, repo.id, "microplate")
        upsert_event(db_session, device.id, "system.microplate.hash", files)
        upsert_repository_file(db_session, repo.id, "core.bin", _HASH_A)

        result = get_device_updates(db_session, device.id)
        assert result == {"microplate": False, "userspace": False}

    def test_microplate_has_update_userspace_clean(self, db_session: Session):
        device = create_device(
            db_session, DeviceCreate(chip_id="M1", node="n1")
        )

        # Microplate — has update
        mp_repo = create_repository(
            db_session,
            RepositoryCreate(name="mp_v1", repo_type="microplate"),
        )
        assign_repo_to_node(db_session, device.id, mp_repo.id, "microplate")
        upsert_event(
            db_session, device.id, "system.microplate.hash", {"core.bin": _HASH_A}
        )
        upsert_repository_file(db_session, mp_repo.id, "core.bin", _HASH_B)

        # Userspace — clean
        us_repo = create_repository(
            db_session,
            RepositoryCreate(name="us_v1", repo_type="userspace"),
        )
        assign_repo_to_node(db_session, device.id, us_repo.id, "userspace")
        upsert_event(
            db_session,
            device.id,
            "system.userspace.hash",
            {"app.bin": _HASH_A},
        )
        upsert_repository_file(db_session, us_repo.id, "app.bin", _HASH_A)

        result = get_device_updates(db_session, device.id)
        assert result == {"microplate": True, "userspace": False}


# ---------------------------------------------------------------------------
# get_repo_file_diff
# ---------------------------------------------------------------------------


class TestGetRepoFileDiff:
    def test_empty_when_hashes_match(self, db_session: Session):
        files = {"core.bin": _HASH_A, "boot.bin": _HASH_B}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=files,
            repo_files=files,
        )
        diff = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert diff == []

    def test_returns_diff_for_changed_file(self, db_session: Session):
        device_hashes = {"core.bin": _HASH_A, "boot.bin": _HASH_B}
        repo_files = {"core.bin": _HASH_A, "boot.bin": "c" * 64}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )
        diff = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert len(diff) == 1
        entry = diff[0]
        assert entry["filename"] == "boot.bin"
        assert entry["device_hash"] == _HASH_B
        assert entry["repo_hash"] == "c" * 64

    def test_file_only_in_repo(self, db_session: Session):
        device_hashes = {"core.bin": _HASH_A}
        repo_files = {"core.bin": _HASH_A, "new.bin": _HASH_B}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )
        diff = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert len(diff) == 1
        entry = diff[0]
        assert entry["filename"] == "new.bin"
        assert entry["device_hash"] is None
        assert entry["repo_hash"] == _HASH_B

    def test_file_only_on_device(self, db_session: Session):
        device_hashes = {"core.bin": _HASH_A, "extra.bin": _HASH_B}
        repo_files = {"core.bin": _HASH_A}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )
        diff = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert len(diff) == 1
        entry = diff[0]
        assert entry["filename"] == "extra.bin"
        assert entry["device_hash"] == _HASH_B
        assert entry["repo_hash"] is None

    def test_empty_when_no_event(self, db_session: Session):
        _, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=None,
            repo_files={"core.bin": _HASH_A},
        )
        device = db_session.query(Device).filter_by(chip_id="DEV01").first()
        diff = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert diff == []

    def test_multiple_diffs_sorted(self, db_session: Session):
        device_hashes = {"a.bin": _HASH_A, "b.bin": _HASH_B, "c.bin": _HASH_A}
        repo_files = {
            "a.bin": _HASH_B,
            "b.bin": _HASH_A,
            "c.bin": _HASH_A,
        }
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )
        diff = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert len(diff) == 2
        assert diff[0]["filename"] == "a.bin"
        assert diff[1]["filename"] == "b.bin"
