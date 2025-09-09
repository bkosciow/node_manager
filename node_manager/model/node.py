from sqlalchemy import create_engine, Column, Integer, String, DateTime, func, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class NodeModel(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    node_name = Column(String(128), index=True)
    node_id = Column(String(256), index=True)
    node_system = Column(JSON)  # JSON type
    node_micropython_hash = Column(JSON)  # JSON type
    node_userspace_hash = Column(JSON)  # JSON type
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, default=func.now())
