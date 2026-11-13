"""CRUD operations for the Device model."""

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.device import Device
from app.schemas.device import DeviceCreate
from app.utils import utcnow


def get_device(db: Session, device_id: int) -> Device | None:
    return db.query(Device).filter(Device.id == device_id).first()


def get_device_by_pair(db: Session, chip_id: str, node: str) -> Device | None:
    return (
        db.query(Device)
        .filter(Device.chip_id == chip_id, Device.node == node)
        .first()
    )


def get_devices(
    db: Session, skip: int = 0, limit: int = 100
) -> list[Device]:
    return (
        db.query(Device)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_device(db: Session, data: DeviceCreate) -> Device:
    db_obj = Device(chip_id=data.chip_id, node=data.node)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def touch_last_seen(db: Session, chip_id: str, node: str) -> None:
    """Refresh last_seen_at for a discovered device (no-op if unknown)."""
    db.execute(
        update(Device)
        .where(Device.chip_id == chip_id, Device.node == node)
        .values(last_seen_at=utcnow())
    )
    db.commit()


def touch_last_updated(db: Session, device_id: int) -> None:
    """Record that the device's data was just updated (event upsert)."""
    db.execute(
        update(Device)
        .where(Device.id == device_id)
        .values(last_updated_at=utcnow())
    )
    db.commit()
