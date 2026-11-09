"""CRUD operations for the DeviceEvent model."""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.device_event import DeviceEvent
from app.utils import utcnow

logger = logging.getLogger(__name__)


def upsert_event(
    db: Session,
    device_id: int,
    event_type: str,
    parameters: dict,
) -> DeviceEvent:
    """Insert or update a DeviceEvent record.

    Single-threaded worker — no race condition between check and write.
    DB unique constraint on (device_id, event_type) is the final guard.
    """
    now = utcnow()
    existing = get_event(db, device_id, event_type)
    if existing is not None:
        existing.parameters = parameters
        existing.updated_at = now
        db.commit()
        return existing

    obj = DeviceEvent(
        device_id=device_id,
        event_type=event_type,
        parameters=parameters,
        updated_at=now,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_event(
    db: Session, device_id: int, event_type: str
) -> DeviceEvent | None:
    """Get a single DeviceEvent by device_id and event_type."""
    return (
        db.query(DeviceEvent)
        .filter(
            DeviceEvent.device_id == device_id,
            DeviceEvent.event_type == event_type,
        )
        .first()
    )


def get_events(db: Session, device_id: int) -> list[DeviceEvent]:
    """Get all DeviceEvents for a device."""
    return (
        db.query(DeviceEvent)
        .filter(DeviceEvent.device_id == device_id)
        .all()
    )


def get_or_create_device(
    db: Session, chip_id: str, node: str
) -> Device:
    """Return existing Device or create a new one.

    Handles IntegrityError (concurrent insert) by rolling back
    and fetching the existing record.
    """
    from app.crud.device import create_device, get_device_by_pair
    from app.schemas.device import DeviceCreate

    existing = get_device_by_pair(db, chip_id, node)
    if existing is not None:
        return existing

    try:
        db_obj = create_device(db, DeviceCreate(chip_id=chip_id, node=node))
        logger.info("Auto-created device: %s (id=%s)", node, db_obj.id)
        return db_obj
    except IntegrityError:
        db.rollback()
        logger.warning(
            "IntegrityError creating device (%s, %s) — "
            "concurrent insert, fetching existing",
            chip_id,
            node,
        )
        return get_device_by_pair(db, chip_id, node)
