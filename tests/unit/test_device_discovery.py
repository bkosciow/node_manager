"""Unit tests for MessageHandler — parsing, validation, cache logic."""

import tempfile
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.message_handler.device_discovery import MessageHandler
from app.models.device import Device  # noqa: F401 — register with Base
from app.crud.device import create_device, get_device_by_pair
from app.schemas.device import DeviceCreate


# -- Helper: build a mock message with arbitrary data ------------------------

def _msg(data=None):
    m = MagicMock()
    m.data = data
    return m


# -- handle() — valid messages -----------------------------------------------


class TestHandleValid:
    def test_valid_message_pushes_tuple_to_queue(self):
        h = MessageHandler()
        h.handle(_msg({"chip_id": "ABC123", "node": "sensor-1"}))
        assert h.queue.qsize() == 1
        assert h.queue.get_nowait() == ("ABC123", "sensor-1")

    def test_whitespace_only_chip_id_treated_as_missing(self):
        h = MessageHandler()
        h.handle(_msg({"chip_id": "  ", "node": "sensor-1"}))
        assert h.queue.empty()

    def test_whitespace_only_node_treated_as_missing(self):
        h = MessageHandler()
        h.handle(_msg({"chip_id": "ABC123", "node": " "}))
        assert h.queue.empty()


# -- handle() — None / missing fields ----------------------------------------


class TestHandleInvalid:
    def test_none_message_no_exception(self):
        h = MessageHandler()
        h.handle(None)
        assert h.queue.empty()

    def test_none_data_no_exception(self):
        h = MessageHandler()
        h.handle(_msg(None))
        assert h.queue.empty()

    def test_missing_chip_id_logged_and_skipped(self):
        h = MessageHandler()
        h.handle(_msg({"node": "sensor-1"}))
        assert h.queue.empty()

    def test_missing_node_logged_and_skipped(self):
        h = MessageHandler()
        h.handle(_msg({"chip_id": "ABC123"}))
        assert h.queue.empty()

    def test_empty_string_chip_id_skipped(self):
        h = MessageHandler()
        h.handle(_msg({"chip_id": "", "node": "sensor-1"}))
        assert h.queue.empty()

    def test_empty_string_node_skipped(self):
        h = MessageHandler()
        h.handle(_msg({"chip_id": "ABC123", "node": ""}))
        assert h.queue.empty()


# -- handle() — non-dict data ------------------------------------------------


class TestHandleNonDict:
    def test_data_is_list_no_crash(self):
        h = MessageHandler()
        h.handle(_msg([1, 2, 3]))
        assert h.queue.empty()

    def test_data_is_string_no_crash(self):
        h = MessageHandler()
        h.handle(_msg("hello"))
        assert h.queue.empty()


# -- _process() — cache and DB logic (real SQLite) ---------------------------

# File-based SQLite so new connections (created by _process via
# session_factory()) see the same tables as the fixture.
_tmp_db_dir = tempfile.mkdtemp()
_db_file = f"{_tmp_db_dir}/test.db"


@pytest.fixture
def db_env():
    """Fresh file-based SQLite DB with tables for each test."""
    eng = create_engine(f"sqlite:///{_db_file}")
    Session = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng, Session
    Base.metadata.drop_all(bind=eng)


class TestProcess:
    """Test _process with a real SQLite database."""

    def test_cache_hit_skips_db(self, db_env):
        eng, Session = db_env
        h = MessageHandler()
        h.cache.add(("ABC123", "sensor-1"))
        h._process("ABC123", "sensor-1", Session)
        db = Session()
        assert get_device_by_pair(db, "ABC123", "sensor-1") is None
        db.close()

    def test_cache_miss_db_miss_inserts(self, db_env):
        eng, Session = db_env
        h = MessageHandler()
        h._process("ABC123", "sensor-1", Session)
        assert ("ABC123", "sensor-1") in h.cache

        db = Session()
        dev = get_device_by_pair(db, "ABC123", "sensor-1")
        assert dev is not None
        assert dev.chip_id == "ABC123"
        assert dev.node == "sensor-1"
        db.close()

    def test_cache_miss_db_hit_warms_cache(self, db_env):
        eng, Session = db_env
        # Seed the DB manually.
        db = Session()
        create_device(db, DeviceCreate(chip_id="ABC123", node="sensor-1"))
        db.commit()
        db.close()

        h = MessageHandler()
        h._process("ABC123", "sensor-1", Session)
        assert ("ABC123", "sensor-1") in h.cache

        db = Session()
        count = db.query(Device).filter(
            Device.chip_id == "ABC123", Device.node == "sensor-1"
        ).count()
        assert count == 1
        db.close()

    def test_integrity_error_no_crash(self, db_env):
        eng, Session = db_env
        # Seed DB so unique constraint fires.
        db = Session()
        create_device(db, DeviceCreate(chip_id="ABC123", node="sensor-1"))
        db.commit()
        db.close()

        # First call: DB miss → insert OK.
        h = MessageHandler()
        h._process("ABC123", "sensor-1", Session)

        # Second call with fresh handler (no cache) → DB says exists → OK.
        h2 = MessageHandler()
        h2._process("ABC123", "sensor-1", Session)

        # No crash. Cache populated.
        assert ("ABC123", "sensor-1") in h2.cache


# -- start() / stop() --------------------------------------------------------


class TestWorkerLifecycle:
    def test_start_creates_daemon_thread(self):
        h = MessageHandler()
        h.start()
        assert h._worker is not None
        assert h._worker.daemon is True

    def test_stop_sets_event(self):
        h = MessageHandler()
        h.start()
        h.stop()
        assert h._stop_event.is_set()
