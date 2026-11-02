"""Device model for IoT device discovery."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.device_event import DeviceEvent
    from app.models.device_ignored_file import DeviceIgnoredFile
    from app.models.node_update import NodeUpdate


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chip_id: Mapped[str] = mapped_column(String(255), nullable=False)
    node: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    events: Mapped[list["DeviceEvent"]] = relationship(
        "DeviceEvent", back_populates="device", cascade="all, delete-orphan"
    )
    repo_assignments: Mapped[list["NodeRepository"]] = relationship(  # noqa: F821
        "NodeRepository", back_populates="device", cascade="all, delete-orphan"
    )
    ignored_files: Mapped[list["DeviceIgnoredFile"]] = relationship(
        "DeviceIgnoredFile",
        back_populates="device",
        cascade="all, delete-orphan",
    )
    updates: Mapped[list["NodeUpdate"]] = relationship(  # noqa: F821
        "NodeUpdate",
        back_populates="device",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("chip_id", "node", name="uq_chip_id_node"),
    )
