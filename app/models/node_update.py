"""NodeUpdate model for operator-triggered upgrade sessions."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.node_update_file import NodeUpdateFile
    from app.models.repository import Repository


class NodeUpdate(Base):
    __tablename__ = "node_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(36), nullable=False)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    repo_type: Mapped[str] = mapped_column(String(50), nullable=False)
    files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    device: Mapped["Device"] = relationship(  # noqa: F821
        "Device", back_populates="updates"
    )
    repository: Mapped["Repository"] = relationship(  # noqa: F821
        "Repository", back_populates="updates"
    )
    progress: Mapped[list["NodeUpdateFile"]] = relationship(  # noqa: F821
        "NodeUpdateFile",
        back_populates="node_update",
        cascade="all, delete-orphan",
        order_by="NodeUpdateFile.filename",
    )

    __table_args__ = (
        UniqueConstraint("token", name="uq_node_update_token"),
    )
