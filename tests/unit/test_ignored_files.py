"""Unit tests for ignored files feature."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.crud.device import create_device
from app.crud.device_event import upsert_event
from app.crud.device_ignored_file import (
    create_ignored_file,
    delete_ignored_file,
    get_ignored_files,
)
from app.crud.node_repository import assign_repo_to_node
from app.crud.repository import (
    create_repository,
    upsert_repository_file,
)
from app.crud.update_status import (
    check_update_available,
    get_repo_file_diff,
)
from app.db.base import Base

# Register all models so tables are created.
from app.models.device import Device  # noqa: F401
from app.models.device_event import DeviceEvent  # noqa: F401
from app.models.device_ignored_file import DeviceIgnoredFile  # noqa: F401
from app.models.node_repository import NodeRepository  # noqa: F401
from app.models.repository import Repository, RepositoryFile  # noqa: F401

from app.schemas.device import DeviceCreate
from app.schemas.device_ignored_file import IgnoredFileCreate
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
    """Create device + repo + assignment + event + repo files in one shot."""
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
# CRUD tests
# ---------------------------------------------------------------------------


class TestIgnoredFileCrud:
    def test_create_and_list(self, db_session: Session):
        device = create_device(
            db_session, DeviceCreate(chip_id="D1", node="n1")
        )
        data = IgnoredFileCreate(repo_type="userspace", filename="my.conf")
        created = create_ignored_file(db_session, device.id, data)

        assert created is not None
        assert created.device_id == device.id
        assert created.repo_type == "userspace"
        assert created.filename == "my.conf"

        listed = get_ignored_files(db_session, device.id)
        assert len(listed) == 1
        assert listed[0].filename == "my.conf"

    def test_create_returns_none_for_missing_device(self, db_session: Session):
        data = IgnoredFileCreate(repo_type="userspace", filename="my.conf")
        result = create_ignored_file(db_session, 9999, data)
        assert result is None

    def test_duplicate_raises_integrity_error(self, db_session: Session):
        device = create_device(
            db_session, DeviceCreate(chip_id="D2", node="n1")
        )
        data = IgnoredFileCreate(repo_type="userspace", filename="my.conf")
        create_ignored_file(db_session, device.id, data)

        with pytest.raises(IntegrityError):
            create_ignored_file(db_session, device.id, data)

    def test_delete_existing(self, db_session: Session):
        device = create_device(
            db_session, DeviceCreate(chip_id="D3", node="n1")
        )
        data = IgnoredFileCreate(repo_type="userspace", filename="my.conf")
        create_ignored_file(db_session, device.id, data)

        deleted = delete_ignored_file(
            db_session, device.id, "userspace", "my.conf"
        )
        assert deleted is True
        assert get_ignored_files(db_session, device.id) == []

    def test_delete_nonexistent_returns_false(self, db_session: Session):
        device = create_device(
            db_session, DeviceCreate(chip_id="D4", node="n1")
        )
        deleted = delete_ignored_file(
            db_session, device.id, "userspace", "nope.conf"
        )
        assert deleted is False

    def test_different_repo_types_allowed(self, db_session: Session):
        device = create_device(
            db_session, DeviceCreate(chip_id="D5", node="n1")
        )
        create_ignored_file(
            db_session, device.id, IgnoredFileCreate(repo_type="microplate", filename="my.conf")
        )
        create_ignored_file(
            db_session, device.id, IgnoredFileCreate(repo_type="userspace", filename="my.conf")
        )

        listed = get_ignored_files(db_session, device.id)
        assert len(listed) == 2
        types = {i.repo_type for i in listed}
        assert types == {"microplate", "userspace"}


# ---------------------------------------------------------------------------
# Hash comparison with ignored files
# ---------------------------------------------------------------------------


class TestHashComparisonWithIgnored:
    def test_ignored_file_excluded_from_diff(self, db_session: Session):
        """File that exists only on device but is ignored should not appear in diff."""
        device_hashes = {"core.bin": _HASH_A, "my.conf": "xyz"}
        repo_files = {"core.bin": _HASH_A}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )

        # Without ignore — my.conf shows up as diff
        diff_before = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert len(diff_before) == 1
        assert diff_before[0]["filename"] == "my.conf"

        # Add ignore
        create_ignored_file(
            db_session,
            device.id,
            IgnoredFileCreate(repo_type="microplate", filename="my.conf"),
        )

        # After ignore — no diff
        diff_after = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert diff_after == []

    def test_ignored_file_excluded_from_update_check(
        self, db_session: Session
    ):
        """check_update_available should ignore marked files."""
        device_hashes = {"core.bin": _HASH_A, "my.conf": "xyz"}
        repo_files = {"core.bin": _HASH_A}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )

        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is True

        create_ignored_file(
            db_session,
            device.id,
            IgnoredFileCreate(repo_type="microplate", filename="my.conf"),
        )

        assert check_update_available(
            db_session, device.id, repo.id, "microplate"
        ) is False

    def test_multiple_ignored_files(self, db_session: Session):
        """Multiple ignored files should all be excluded."""
        device_hashes = {
            "core.bin": _HASH_A,
            "my.conf": "abc",
            "debug.log": "def",
            "cache.dat": "ghi",
        }
        repo_files = {"core.bin": _HASH_A}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )

        # Ignore two files
        create_ignored_file(
            db_session,
            device.id,
            IgnoredFileCreate(repo_type="microplate", filename="my.conf"),
        )
        create_ignored_file(
            db_session,
            device.id,
            IgnoredFileCreate(repo_type="microplate", filename="debug.log"),
        )

        diff = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert len(diff) == 1
        assert diff[0]["filename"] == "cache.dat"

    def test_remove_ignore_restores_diff(self, db_session: Session):
        """Removing an ignored file should make it appear in diff again."""
        device_hashes = {"core.bin": _HASH_A, "my.conf": "xyz"}
        repo_files = {"core.bin": _HASH_A}
        device, repo = _setup_device_with_repo_and_event(
            db_session,
            device_hashes=device_hashes,
            repo_files=repo_files,
        )

        create_ignored_file(
            db_session,
            device.id,
            IgnoredFileCreate(repo_type="microplate", filename="my.conf"),
        )
        assert get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        ) == []

        delete_ignored_file(
            db_session, device.id, "microplate", "my.conf"
        )
        diff = get_repo_file_diff(
            db_session, device.id, repo.id, "microplate"
        )
        assert len(diff) == 1
        assert diff[0]["filename"] == "my.conf"

    def test_ignored_file_in_other_repo_type_no_effect(
        self, db_session: Session
    ):
        """Ignoring a file for microplate should not affect userspace diff."""
        device = create_device(
            db_session, DeviceCreate(chip_id="D6", node="n1")
        )

        # Microplate repo
        mp_repo = create_repository(
            db_session,
            RepositoryCreate(name="mp_v1", repo_type="microplate"),
        )
        assign_repo_to_node(db_session, device.id, mp_repo.id, "microplate")
        upsert_event(
            db_session,
            device.id,
            "system.microplate.hash",
            {"core.bin": _HASH_A, "my.conf": "xyz"},
        )
        upsert_repository_file(db_session, mp_repo.id, "core.bin", _HASH_A)

        # Ignore my.conf for microplate
        create_ignored_file(
            db_session,
            device.id,
            IgnoredFileCreate(repo_type="microplate", filename="my.conf"),
        )

        # Microplate diff should be empty
        mp_diff = get_repo_file_diff(
            db_session, device.id, mp_repo.id, "microplate"
        )
        assert mp_diff == []

        # Userspace repo with same extra file — should show diff
        us_repo = create_repository(
            db_session,
            RepositoryCreate(name="us_v1", repo_type="userspace"),
        )
        assign_repo_to_node(db_session, device.id, us_repo.id, "userspace")
        upsert_event(
            db_session,
            device.id,
            "system.userspace.hash",
            {"app.bin": _HASH_A, "my.conf": "xyz"},
        )
        upsert_repository_file(db_session, us_repo.id, "app.bin", _HASH_A)

        us_diff = get_repo_file_diff(
            db_session, device.id, us_repo.id, "userspace"
        )
        assert len(us_diff) == 1
        assert us_diff[0]["filename"] == "my.conf"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestIgnoredFileSchema:
    def test_valid_create(self):
        data = IgnoredFileCreate(repo_type="userspace", filename="my.conf")
        assert data.repo_type == "userspace"
        assert data.filename == "my.conf"

    def test_invalid_repo_type_raises(self):
        with pytest.raises(Exception):
            IgnoredFileCreate(repo_type="invalid", filename="my.conf")

    def test_empty_filename_raises(self):
        with pytest.raises(Exception):
            IgnoredFileCreate(repo_type="userspace", filename="")

    def test_whitespace_filename_raises(self):
        with pytest.raises(Exception):
            IgnoredFileCreate(repo_type="userspace", filename="   ")

    def test_filename_is_stripped(self):
        data = IgnoredFileCreate(repo_type="userspace", filename="  my.conf  ")
        assert data.filename == "my.conf"
