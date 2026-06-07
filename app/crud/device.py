"""CRUD operations for the Device model."""

from sqlalchemy.orm import Session

from app.models.device import Device
from app.schemas.device import DeviceCreate


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
