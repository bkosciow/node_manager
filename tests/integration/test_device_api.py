"""Integration tests for REST API endpoints."""

from app.crud.device import create_device, touch_last_updated
from app.schemas.device import DeviceCreate

from tests.conftest import SAMPLE_DEVICE_1, SAMPLE_DEVICE_2, SAMPLE_DEVICE_3


# -- GET /api/devices --------------------------------------------------------


class TestListDevices:
    def test_empty_db_returns_empty_array(self, client):
        resp = client.get("/api/devices")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_devices_with_all_fields(self, client, test_db):
        for d in [SAMPLE_DEVICE_1, SAMPLE_DEVICE_2]:
            create_device(test_db, DeviceCreate(**d))
        test_db.commit()

        resp = client.get("/api/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        for dev in data:
            assert "id" in dev
            assert "chip_id" in dev
            assert "node" in dev
            assert "created_at" in dev
            assert "last_seen_at" in dev
            assert "last_updated_at" in dev

    def test_last_updated_at_is_none_before_event(self, client, test_db):
        create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
        test_db.commit()

        resp = client.get("/api/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["last_seen_at"] is not None
        assert data[0]["last_updated_at"] is None

    def test_last_updated_at_set_after_touch(self, client, test_db):
        dev = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
        test_db.commit()

        touch_last_updated(test_db, dev.id)
        test_db.commit()

        resp = client.get("/api/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["last_updated_at"] is not None

    def test_pagination_skip_and_limit(self, client, test_db):
        for d in [SAMPLE_DEVICE_1, SAMPLE_DEVICE_2, SAMPLE_DEVICE_3]:
            create_device(test_db, DeviceCreate(**d))
        test_db.commit()

        resp = client.get("/api/devices?skip=1&limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    def test_limit_exceeds_max_returns_422(self, client):
        resp = client.get("/api/devices?limit=1001")
        assert resp.status_code == 422

    def test_limit_zero_returns_422(self, client):
        resp = client.get("/api/devices?limit=0")
        assert resp.status_code == 422

    def test_skip_negative_returns_422(self, client):
        resp = client.get("/api/devices?skip=-1")
        assert resp.status_code == 422


# -- GET /api/devices/{device_id} -------------------------------------------


class TestGetSingleDevice:
    def test_existing_device_returns_200(self, client, test_db):
        dev = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
        test_db.commit()

        resp = client.get(f"/api/devices/{dev.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chip_id"] == SAMPLE_DEVICE_1["chip_id"]
        assert data["node"] == SAMPLE_DEVICE_1["node"]
        assert "last_seen_at" in data
        assert "last_updated_at" in data
        assert data["last_updated_at"] is None
        assert "events" in data
        assert data["events"] == {}

    def test_nonexistent_device_returns_404(self, client):
        resp = client.get("/api/devices/9999")
        assert resp.status_code == 404

    def test_device_id_zero_returns_422(self, client):
        resp = client.get("/api/devices/0")
        assert resp.status_code == 422
