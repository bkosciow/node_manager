"""Unit tests for Device CRUD operations using SQLite in-memory."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.crud.device import (
    create_device,
    get_device,
    get_device_by_pair,
    get_devices,
    touch_last_seen,
    touch_last_updated,
)
from app.models.device import Device  # noqa: F401 — register model with Base
from app.schemas.device import DeviceCreate

# In-memory SQLite.
engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _session():
    s = TestingSession()
    try:
        yield s
    finally:
        s.close()


# -- create_device -----------------------------------------------------------


class TestCreateDevice:
    def test_create_returns_device_with_id(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        assert dev.id is not None
        assert dev.id > 0
        assert dev.chip_id == "ABC123"
        assert dev.node == "s1"
        assert dev.created_at is not None
        assert dev.last_seen_at is not None
        assert dev.last_updated_at is None


# -- get_device --------------------------------------------------------------


class TestGetDevice:
    def test_get_existing(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        found = get_device(db, dev.id)
        assert found is not None
        assert found.chip_id == "ABC123"

    def test_get_missing_returns_none(self):
        db = next(_session())
        assert get_device(db, 9999) is None


# -- get_device_by_pair ------------------------------------------------------


class TestGetDeviceByPair:
    def test_get_matching_pair(self):
        db = next(_session())
        create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        found = get_device_by_pair(db, "ABC123", "s1")
        assert found is not None

    def test_get_non_matching_returns_none(self):
        db = next(_session())
        create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        assert get_device_by_pair(db, "ABC123", "s2") is None
        assert get_device_by_pair(db, "ZZZZ", "s1") is None


# -- get_devices -------------------------------------------------------------


class TestGetDevices:
    def test_returns_all(self):
        db = next(_session())
        create_device(db, DeviceCreate(chip_id="A", node="s1"))
        create_device(db, DeviceCreate(chip_id="B", node="s2"))
        assert len(get_devices(db)) == 2

    def test_respects_skip_and_limit(self):
        db = next(_session())
        create_device(db, DeviceCreate(chip_id="A", node="s1"))
        create_device(db, DeviceCreate(chip_id="B", node="s2"))
        create_device(db, DeviceCreate(chip_id="C", node="s3"))
        page = get_devices(db, skip=1, limit=1)
        assert len(page) == 1
        assert page[0].chip_id == "B"


# -- unique constraint -------------------------------------------------------


class TestUniqueConstraint:
    def test_duplicate_insert_raises_integrity_error(self):
        db = next(_session())
        create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        with pytest.raises(IntegrityError):
            create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))


# -- touch_last_seen ---------------------------------------------------------


class TestTouchLastSeen:
    def test_refreshes_existing_pair(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        before = dev.last_seen_at
        assert before is not None

        touch_last_seen(db, "ABC123", "s1")
        found = get_device_by_pair(db, "ABC123", "s1")
        assert found.last_seen_at >= before

    def test_unknown_pair_is_noop(self):
        db = next(_session())
        touch_last_seen(db, "ZZZZ", "s9")
        assert get_device_by_pair(db, "ZZZZ", "s9") is None


# -- touch_last_updated ------------------------------------------------------


class TestTouchLastUpdated:
    def test_sets_last_updated_at(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        assert dev.last_updated_at is None

        touch_last_updated(db, dev.id)
        found = get_device(db, dev.id)
        assert found.last_updated_at is not None

    def test_missing_device_is_noop(self):
        db = next(_session())
        touch_last_updated(db, 9999)
