"""Device model for IoT device discovery."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chip_id: Mapped[str] = mapped_column(String(255), nullable=False)
    node: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("chip_id", "node", name="uq_chip_id_node"),
    )
