"""DeviceIgnoredFile model for per-device file ignore lists."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.device import Device


class DeviceIgnoredFile(Base):
    __tablename__ = "device_ignored_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    repo_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    ignored_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    device: Mapped["Device"] = relationship(
        "Device", back_populates="ignored_files"
    )

    __table_args__ = (
        UniqueConstraint(
            "device_id", "repo_type", "filename",
            name="uq_device_repo_filename",
        ),
    )
