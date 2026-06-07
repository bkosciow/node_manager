"""Unit tests for DeviceEvent Pydantic schemas."""

from datetime import datetime

from app.schemas.device_event import (
    DeviceEventResponse,
    SupportedEventTypes,
)


class TestDeviceEventResponse:
    def test_create_from_attributes(self):
        resp = DeviceEventResponse(
            id=1,
            device_id=1,
            event_type="system.pong",
            parameters={"heap_free": 61152},
            updated_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        assert resp.id == 1
        assert resp.device_id == 1
        assert resp.event_type == "system.pong"
        assert resp.parameters == {"heap_free": 61152}
        assert resp.updated_at == datetime(2026, 1, 1, 12, 0, 0)

    def test_parameters_accepts_nested_dict(self):
        resp = DeviceEventResponse(
            id=1,
            device_id=1,
            event_type="system.pong",
            parameters={"ip": ["192.168.1.1", "255.255.255.0"]},
            updated_at=datetime(2026, 1, 1),
        )
        assert resp.parameters["ip"] == ["192.168.1.1", "255.255.255.0"]


class TestSupportedEventTypes:
    def test_all_contains_three_types(self):
        assert len(SupportedEventTypes.ALL) == 3

    def test_pong_in_all(self):
        assert "system.pong" in SupportedEventTypes.ALL

    def test_microplate_hash_in_all(self):
        assert "system.microplate.hash" in SupportedEventTypes.ALL

    def test_userspace_hash_in_all(self):
        assert "system.userspace.hash" in SupportedEventTypes.ALL
