from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from sqlalchemy.orm import relationship
from enum import Enum

Base = declarative_base()


class UpgradeStatus(Enum):
    NEW = "new"
    PENDING = "pending"
    ERROR = "error"
    DONE = "done"
    ABORTED = "aborted"


class NodeModel(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    node_name = Column(String(128), index=True)
    node_id = Column(String(256), index=True)
    node_system = Column(JSON)  # JSON type
    node_micropython_hash = Column(JSON)  # JSON type
    node_userspace_hash = Column(JSON)  # JSON type
    microplate_repository = Column(String(512), nullable=False)
    userspace_repository = Column(String(512), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, default=func.now())


class NodeUpgrade(Base):
    __tablename__ = 'node_upgrades'

    id = Column(Integer, primary_key=True)
    token = Column(String(128), nullable=False)
    type = Column(String(128), nullable=False)
    status = Column(SQLEnum(UpgradeStatus), default=UpgradeStatus.NEW)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    node_id = Column(Integer, ForeignKey('nodes.id'))  # Reference to NodeModel
