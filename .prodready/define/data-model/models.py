# SQLAlchemy models for Device and Repository entities
# This is a design-phase artifact — the final version lives in app/models/

from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chip_id: Mapped[str] = mapped_column(String(255), nullable=False)
    node: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    repo_assignments: Mapped[list["NodeRepository"]] = relationship(
        "NodeRepository", back_populates="device", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("chip_id", "node", name="uq_chip_id_node"),
    )


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    files: Mapped[list["RepositoryFile"]] = relationship(
        "RepositoryFile", back_populates="repository", cascade="all, delete-orphan"
    )
    node_assignments: Mapped[list["NodeRepository"]] = relationship(
        "NodeRepository", back_populates="repository"
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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="files")

    __table_args__ = (
        UniqueConstraint("repository_id", "filename", name="uq_repo_file"),
    )


class NodeRepository(Base):
    __tablename__ = "node_repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    repo_type: Mapped[str] = mapped_column(String(50), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="repo_assignments")
    repository: Mapped["Repository"] = relationship("Repository", back_populates="node_assignments")

    __table_args__ = (
        UniqueConstraint("device_id", "repo_type", name="uq_device_repo_type"),
    )
