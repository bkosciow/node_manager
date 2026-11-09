"""Repository and RepositoryFile models for software repository management."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils import utcnow

if TYPE_CHECKING:
    from app.models.node_update import NodeUpdate


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow
    )

    files: Mapped[list["RepositoryFile"]] = relationship(
        "RepositoryFile", back_populates="repository", cascade="all, delete-orphan"
    )
    node_assignments: Mapped[list["NodeRepository"]] = relationship(  # noqa: F821
        "NodeRepository", back_populates="repository"
    )
    updates: Mapped[list["NodeUpdate"]] = relationship(  # noqa: F821
        "NodeUpdate", back_populates="repository"
    )

    __table_args__ = (
        UniqueConstraint("name", "repo_type", name="uq_repo_name_type"),
    )


class RepositoryFile(Base):
    __tablename__ = "repository_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow
    )

    repository: Mapped["Repository"] = relationship(
        "Repository", back_populates="files"
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "filename", name="uq_repo_file"),
    )
