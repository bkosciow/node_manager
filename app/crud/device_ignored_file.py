"""CRUD operations for DeviceIgnoredFile."""

from sqlalchemy.orm import Session

from app.models.device_ignored_file import DeviceIgnoredFile
from app.schemas.device_ignored_file import IgnoredFileCreate


def get_ignored_files(db: Session, device_id: int) -> list[DeviceIgnoredFile]:
    """Get all ignored files for a device."""
    return (
        db.query(DeviceIgnoredFile)
        .filter(DeviceIgnoredFile.device_id == device_id)
        .all()
    )


def create_ignored_file(
    db: Session, device_id: int, data: IgnoredFileCreate
) -> DeviceIgnoredFile | None:
    """Add an ignored file for a device.

    Returns None if device doesn't exist. Raises IntegrityError if
    the file is already ignored (caller should catch and return 409).
    """
    from app.models.device import Device

    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        return None

    db_obj = DeviceIgnoredFile(
        device_id=device_id,
        repo_type=data.repo_type,
        filename=data.filename,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_ignored_file(
    db: Session, device_id: int, repo_type: str, filename: str
) -> bool:
    """Remove an ignored file for a device.

    Returns True if a row was deleted, False if not found.
    """
    result = (
        db.query(DeviceIgnoredFile)
        .filter(
            DeviceIgnoredFile.device_id == device_id,
            DeviceIgnoredFile.repo_type == repo_type,
            DeviceIgnoredFile.filename == filename,
        )
        .delete()
    )
    if result:
        db.commit()
    return result > 0
