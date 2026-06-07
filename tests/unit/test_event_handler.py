"""Unit tests for event detection in MessageHandler."""

from unittest.mock import MagicMock

from app.message_handler.device_discovery import (
    MessageHandler,
    SUPPORTED_EVENTS,
)


def _msg(data=None):
    m = MagicMock()
    m.data = data
    return m


# -- Event detection in handle() --------------------------------------------


class TestEventDetection:
    def test_system_pong_event_queues_event_tuple(self):
        h = MessageHandler()
        h.handle(_msg({
            "chip_id": "ABC123",
            "node": "sensor-1",
            "event": "system.pong",
            "parameters": {"heap_free": 61152},
        }))
        assert h.queue.qsize() == 2
        # First item: device discovery tuple.
        item1 = h.queue.get_nowait()
        assert item1 == ("device", "ABC123", "sensor-1")
        # Second item: event tuple.
        item2 = h.queue.get_nowait()
        assert item2 == ("event", "ABC123", "sensor-1", "system.pong", {
            "heap_free": 61152
        })

    def test_system_microplate_hash_event_queues_event_tuple(self):
        h = MessageHandler()
        h.handle(_msg({
            "chip_id": "ABC123",
            "node": "sensor-1",
            "event": "system.microplate.hash",
            "parameters": {"file1.bin": "abc123"},
        }))
        assert h.queue.qsize() == 2
        device_item = h.queue.get_nowait()
        assert device_item[0] == "device"
        event_item = h.queue.get_nowait()
        assert event_item[0] == "event"
        assert event_item[3] == "system.microplate.hash"
        assert event_item[4] == {"file1.bin": "abc123"}

    def test_system_userspace_hash_event_queues_event_tuple(self):
        h = MessageHandler()
        h.handle(_msg({
            "chip_id": "ABC123",
            "node": "sensor-1",
            "event": "system.userspace.hash",
            "parameters": {"main.py": "def456"},
        }))
        assert h.queue.qsize() == 2
        assert h.queue.get_nowait()[0] == "device"
        event_item = h.queue.get_nowait()
        assert event_item[3] == "system.userspace.hash"

    def test_unrecognized_event_only_queues_device_tuple(self):
        h = MessageHandler()
        h.handle(_msg({
            "chip_id": "ABC123",
            "node": "sensor-1",
            "event": "system.unknown",
            "parameters": {},
        }))
        assert h.queue.qsize() == 1
        item = h.queue.get_nowait()
        assert item == ("device", "ABC123", "sensor-1")

    def test_no_event_field_only_queues_device_tuple(self):
        h = MessageHandler()
        h.handle(_msg({
            "chip_id": "ABC123",
            "node": "sensor-1",
        }))
        assert h.queue.qsize() == 1
        item = h.queue.get_nowait()
        assert item == ("device", "ABC123", "sensor-1")

    def test_missing_parameters_defaults_to_empty_dict(self):
        h = MessageHandler()
        h.handle(_msg({
            "chip_id": "ABC123",
            "node": "sensor-1",
            "event": "system.pong",
            # No 'parameters' key.
        }))
        assert h.queue.qsize() == 2
        h.queue.get_nowait()  # device tuple
        event_item = h.queue.get_nowait()
        assert event_item[4] == {}


# -- Worker dispatch --------------------------------------------------------


class TestWorkerDispatch:
    def test_dispatch_device_tag_calls_process(self):
        h = MessageHandler()
        # Mock _process to avoid DB access.
        h._process = lambda cid, node, sf: None  # noqa: ARG005
        h.queue.put(("device", "ABC123", "sensor-1"))
        # Manually run one iteration of the loop.
        item = h.queue.get_nowait()
        assert item[0] == "device"

    def test_dispatch_event_tag_calls_process_event(self):
        h = MessageHandler()
        # Mock _process_event.
        h._process_event = lambda cid, node, et, params, sf: None  # noqa: ARG005
        h.queue.put((
            "event", "ABC123", "sensor-1", "system.pong", {"heap_free": 100}
        ))
        item = h.queue.get_nowait()
        assert item[0] == "event"
        assert item[3] == "system.pong"


# -- SUPPORTED_EVENTS constant -----------------------------------------------


class TestSupportedEvents:
    def test_contains_pong(self):
        assert "system.pong" in SUPPORTED_EVENTS

    def test_contains_microplate_hash(self):
        assert "system.microplate.hash" in SUPPORTED_EVENTS

    def test_contains_userspace_hash(self):
        assert "system.userspace.hash" in SUPPORTED_EVENTS

    def test_is_frozenset(self):
        assert isinstance(SUPPORTED_EVENTS, frozenset)
