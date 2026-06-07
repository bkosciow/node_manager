# DeviceEvent model — reference for implementation
# To be added to app/models/device.py or a new app/models/device_event.py

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DeviceEvent(Base):
    __tablename__ = "device_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict] = mapped_column(
        # Use JSONB on PostgreSQL, JSON on SQLite
        # Implementation should handle dialect difference
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationship back to Device
    device: Mapped["Device"] = relationship("Device", back_populates="events")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("device_id", "event_type", name="uq_device_event_type"),
    )
