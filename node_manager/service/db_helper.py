from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect
from sqlalchemy import create_engine
from node_manager.model.node import NodeModel
from node_manager.model.microplate import MicroplateHash
from node_manager.model.userspace import UserspaceHash
import logging
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)
cfg = None
Base = None


def get_db():
    if cfg is None:
        yield None
    else:
        engine = create_engine(cfg['db'], echo=False)
        #Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def check_and_create_tables():
    db = next(get_db())
    inspector = inspect(db.bind)

    tables_to_create = [NodeModel.__table__, MicroplateHash.__table__, UserspaceHash.__table__]

    for table in tables_to_create:
        if not inspector.has_table(table.name):
            logger.info(f"Table '{table.name}' does not exist. Creating...")
            Base.metadata.create_all(bind=db.bind, tables=[table])
