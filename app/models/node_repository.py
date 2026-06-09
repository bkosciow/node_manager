"""NodeRepository model for repo-to-node assignments."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NodeRepository(Base):
    __tablename__ = "node_repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    repo_type: Mapped[str] = mapped_column(String(50), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    device: Mapped["Device"] = relationship(  # noqa: F821
        "Device", back_populates="repo_assignments"
    )
    repository: Mapped["Repository"] = relationship(  # noqa: F821
        "Repository", back_populates="node_assignments"
    )

    __table_args__ = (
        UniqueConstraint(
            "device_id", "repo_type", name="uq_device_repo_type"
        ),
    )
