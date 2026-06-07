"""Shared test fixtures."""

import pytest
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.rest_server import app

# Use a temporary file-based SQLite so all connections (including the one
# spawned by TestClient in a separate thread) see the same database.
_tmp_dir = tempfile.mkdtemp()
_db_file = f"{_tmp_dir}/test.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_db_file}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    """FastAPI TestClient with a fresh database per test."""
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_db():
    """Return a session bound to the test database for seeding data."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# -- Sample data -------------------------------------------------------------

SAMPLE_DEVICE_1 = {"chip_id": "ABC123", "node": "sensor-1"}
SAMPLE_DEVICE_2 = {"chip_id": "DEF456", "node": "sensor-2"}
SAMPLE_DEVICE_3 = {"chip_id": "ABC123", "node": "sensor-2"}
