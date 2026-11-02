from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.db.base import Base

# Import models so Base.metadata.create_all() knows about all tables.
# flake8: noqa: F401
from app.models.device import Device
from app.models.device_event import DeviceEvent
from app.models.node_repository import NodeRepository
from app.models.node_update import NodeUpdate
from app.models.repository import Repository, RepositoryFile

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
