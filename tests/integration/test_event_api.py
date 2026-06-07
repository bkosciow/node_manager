"""Integration tests for event API endpoints."""

from app.crud.device import create_device
from app.crud.device_event import upsert_event
from app.schemas.device import DeviceCreate


# -- GET /api/devices/{device_id}/events/{event_type} ------------------------


class TestGetDeviceEvent:
    def test_returns_parameters_for_existing_event(self, client, test_db):
        dev = create_device(test_db, DeviceCreate(
            chip_id="ABC123", node="sensor-1"
        ))
        test_db.commit()
        upsert_event(
            test_db, dev.id, "system.pong",
            {"heap_free": 61152, "platform": "esp32"},
        )
        test_db.commit()

        resp = client.get(f"/api/devices/{dev.id}/events/system.pong")
        assert resp.status_code == 200
        data = resp.json()
        assert data["heap_free"] == 61152
        assert data["platform"] == "esp32"

    def test_returns_404_when_event_type_not_stored(self, client, test_db):
        dev = create_device(test_db, DeviceCreate(
            chip_id="ABC123", node="sensor-1"
        ))
        test_db.commit()

        resp = client.get(f"/api/devices/{dev.id}/events/system.pong")
        assert resp.status_code == 404

    def test_returns_404_when_device_not_found(self, client):
        resp = client.get("/api/devices/9999/events/system.pong")
        assert resp.status_code == 404

    def test_returns_400_for_unsupported_event_type(self, client, test_db):
        dev = create_device(test_db, DeviceCreate(
            chip_id="ABC123", node="sensor-1"
        ))
        test_db.commit()

        resp = client.get(f"/api/devices/{dev.id}/events/invalid.event")
        assert resp.status_code == 400

    def test_returns_422_for_invalid_device_id(self, client):
        resp = client.get("/api/devices/0/events/system.pong")
        assert resp.status_code == 422


# -- GET /api/devices/{device_id}/events -------------------------------------


class TestGetDeviceEvents:
    def test_returns_all_events_keyed_by_type(self, client, test_db):
        dev = create_device(test_db, DeviceCreate(
            chip_id="ABC123", node="sensor-1"
        ))
        test_db.commit()
        upsert_event(
            test_db, dev.id, "system.pong",
            {"heap_free": 61152},
        )
        upsert_event(
            test_db, dev.id, "system.microplate.hash",
            {"file1.bin": "abc123"},
        )
        test_db.commit()

        resp = client.get(f"/api/devices/{dev.id}/events")
        assert resp.status_code == 200
        data = resp.json()
        assert "system.pong" in data
        assert "system.microplate.hash" in data
        assert data["system.pong"]["heap_free"] == 61152
        assert data["system.microplate.hash"]["file1.bin"] == "abc123"

    def test_returns_empty_dict_when_no_events(self, client, test_db):
        dev = create_device(test_db, DeviceCreate(
            chip_id="ABC123", node="sensor-1"
        ))
        test_db.commit()

        resp = client.get(f"/api/devices/{dev.id}/events")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_returns_404_when_device_not_found(self, client):
        resp = client.get("/api/devices/9999/events")
        assert resp.status_code == 404

    def test_returns_422_for_invalid_device_id(self, client):
        resp = client.get("/api/devices/0/events")
        assert resp.status_code == 422
