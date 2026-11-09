"""NodeUpdateFile model for per-file progress rows in upgrade sessions."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils import utcnow

if TYPE_CHECKING:
    from app.models.node_update import NodeUpdate


class NodeUpdateFile(Base):
    __tablename__ = "node_update_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_update_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("node_updates.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    node_update: Mapped["NodeUpdate"] = relationship(  # noqa: F821
        "NodeUpdate", back_populates="progress"
    )

    __table_args__ = (
        UniqueConstraint("node_update_id", "filename", name="uq_node_update_file"),
    )
