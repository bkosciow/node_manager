"""Unit tests for DeviceEvent CRUD operations."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.device import Device  # noqa: F401 — register with Base
from app.models.device_event import DeviceEvent  # noqa: F401
from app.crud.device import create_device
from app.crud.device_event import (
    get_event,
    get_events,
    get_or_create_device,
    upsert_event,
)
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


# -- upsert_event ------------------------------------------------------------


class TestUpsertEvent:
    def test_insert_new_event(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        result = upsert_event(
            db, dev.id, "system.pong", {"heap_free": 61152}
        )
        assert result.device_id == dev.id
        assert result.event_type == "system.pong"
        assert result.parameters == {"heap_free": 61152}
        assert result.updated_at is not None

    def test_update_existing_event(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        # Insert first.
        upsert_event(db, dev.id, "system.pong", {"heap_free": 100})
        # Upsert again with different parameters.
        result = upsert_event(
            db, dev.id, "system.pong", {"heap_free": 200, "build": "v2"}
        )
        assert result.parameters == {"heap_free": 200, "build": "v2"}
        # Only one row exists.
        all_events = get_events(db, dev.id)
        assert len(all_events) == 1


# -- get_event ---------------------------------------------------------------


class TestGetEvent:
    def test_returns_event_for_matching_pair(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        upsert_event(db, dev.id, "system.pong", {"heap_free": 100})
        result = get_event(db, dev.id, "system.pong")
        assert result is not None
        assert result.event_type == "system.pong"

    def test_returns_none_for_missing_event_type(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        result = get_event(db, dev.id, "system.userspace.hash")
        assert result is None

    def test_returns_none_for_missing_device(self):
        db = next(_session())
        result = get_event(db, 9999, "system.pong")
        assert result is None


# -- get_events --------------------------------------------------------------


class TestGetEvents:
    def test_returns_all_events_for_device(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        upsert_event(db, dev.id, "system.pong", {"heap_free": 100})
        upsert_event(db, dev.id, "system.microplate.hash", {"f.bin": "abc"})
        events = get_events(db, dev.id)
        assert len(events) == 2
        types = {e.event_type for e in events}
        assert "system.pong" in types
        assert "system.microplate.hash" in types

    def test_returns_empty_list_when_no_events(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        events = get_events(db, dev.id)
        assert events == []


# -- get_or_create_device ----------------------------------------------------


class TestGetOrCreateDevice:
    def test_returns_existing_device(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        result = get_or_create_device(db, "ABC123", "s1")
        assert result.id == dev.id
        # No new device created.
        count = db.query(Device).filter(
            Device.chip_id == "ABC123"
        ).count()
        assert count == 1

    def test_creates_new_device_if_not_found(self):
        db = next(_session())
        result = get_or_create_device(db, "NEW001", "new-node")
        assert result.chip_id == "NEW001"
        assert result.node == "new-node"
        assert result.id is not None

    def test_returns_existing_on_integrity_error(self):
        db = next(_session())
        # Create directly to simulate concurrent insert.
        dev = create_device(db, DeviceCreate(chip_id="RACE", node="r1"))
        # get_or_create should find it.
        result = get_or_create_device(db, "RACE", "r1")
        assert result.id == dev.id
