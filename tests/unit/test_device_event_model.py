"""Unit tests for DeviceEvent model — structure, constraints, relationships."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.device import Device  # noqa: F401 — register with Base
from app.models.device_event import DeviceEvent  # noqa: F401 — register with Base
from app.crud.device import create_device
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


# -- Model structure ---------------------------------------------------------


class TestModelStructure:
    def test_create_device_event_has_all_fields(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        event = DeviceEvent(
            device_id=dev.id,
            event_type="system.pong",
            parameters={"heap_free": 61152},
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        assert event.id is not None
        assert event.id > 0
        assert event.device_id == dev.id
        assert event.event_type == "system.pong"
        assert event.parameters == {"heap_free": 61152}
        assert event.updated_at is not None


# -- Unique constraint on (device_id, event_type) ---------------------------


class TestUniqueConstraint:
    def test_duplicate_device_event_raises_integrity_error(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        db.add(DeviceEvent(
            device_id=dev.id,
            event_type="system.pong",
            parameters={"heap_free": 100},
        ))
        db.commit()

        with pytest.raises(IntegrityError):
            db.add(DeviceEvent(
                device_id=dev.id,
                event_type="system.pong",
                parameters={"heap_free": 200},
            ))
            db.commit()

    def test_different_event_type_same_device_allowed(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        db.add(DeviceEvent(
            device_id=dev.id,
            event_type="system.pong",
            parameters={"heap_free": 100},
        ))
        db.add(DeviceEvent(
            device_id=dev.id,
            event_type="system.microplate.hash",
            parameters={"file1.bin": "abc"},
        ))
        db.commit()

        count = db.query(DeviceEvent).filter(
            DeviceEvent.device_id == dev.id
        ).count()
        assert count == 2


# -- FK cascade delete -------------------------------------------------------


class TestCascadeDelete:
    def test_deleting_device_removes_events(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        db.add(DeviceEvent(
            device_id=dev.id,
            event_type="system.pong",
            parameters={"heap_free": 100},
        ))
        db.commit()

        db.delete(dev)
        db.commit()

        remaining = db.query(DeviceEvent).filter(
            DeviceEvent.device_id == dev.id
        ).count()
        assert remaining == 0


# -- Relationships -----------------------------------------------------------


class TestRelationships:
    def test_device_events_relationship(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        db.add(DeviceEvent(
            device_id=dev.id,
            event_type="system.pong",
            parameters={"heap_free": 100},
        ))
        db.commit()

        # Reload to enable relationship loading.
        db.refresh(dev)
        assert len(dev.events) == 1
        assert dev.events[0].event_type == "system.pong"

    def test_event_device_relationship(self):
        db = next(_session())
        dev = create_device(db, DeviceCreate(chip_id="ABC123", node="s1"))
        event = DeviceEvent(
            device_id=dev.id,
            event_type="system.pong",
            parameters={"heap_free": 100},
        )
        db.add(event)
        db.commit()

        # Reload.
        db.refresh(event)
        assert event.device.id == dev.id
        assert event.device.chip_id == "ABC123"
