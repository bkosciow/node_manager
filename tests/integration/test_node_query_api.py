"""Integration tests for the device active-query REST endpoints (SPEC-006)."""

import pytest

from app.config import settings
from app.crud.device import create_device
from app.schemas.device import DeviceCreate
from app.schemas.repository import VALID_REPO_TYPES
from app.services import comm

from tests.conftest import SAMPLE_DEVICE_1


def _seed_device(test_db):
    return create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))


# -- POST /api/devices/{device_id}/ping --------------------------------------


class TestPingDevice:
    def test_ping_broadcasts_and_returns_202(
        self, client, test_db, monkeypatch
    ):
        """AC: 202, exact UDP payload, hand-built response dict."""
        device = _seed_device(test_db)
        sent: list = []
        monkeypatch.setattr(settings, "node_listener", "192.168.1.99")
        monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))

        resp = client.post(f"/api/devices/{device.id}/ping")

        assert resp.status_code == 202
        assert resp.json() == {
            "message": "Ping broadcast sent",
            "event": "system.ping",
            "target": device.node,
        }

        assert len(sent) == 1
        # Absence of the "parameters" key is part of the assertion.
        assert sent[0] == {"event": "system.ping", "targets": [device.node]}

    def test_unknown_device_returns_404(self, client, monkeypatch):
        """AC: missing device -> 404, nothing broadcast."""
        sent: list = []
        monkeypatch.setattr(settings, "node_listener", "192.168.1.99")
        monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))

        resp = client.post("/api/devices/9999/ping")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Device not found"
        assert sent == []

    def test_listener_not_configured_returns_503(
        self, client, test_db, monkeypatch
    ):
        """AC: empty node_listener -> 503, nothing broadcast."""
        device = _seed_device(test_db)
        sent: list = []
        monkeypatch.setattr(settings, "node_listener", "")
        monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))

        resp = client.post(f"/api/devices/{device.id}/ping")

        assert resp.status_code == 503
        assert resp.json()["detail"] == "Node listener not configured"
        assert sent == []


# -- POST /api/devices/{device_id}/rescan/{repo_type} -------------------------


class TestRescanDevice:
    @pytest.mark.parametrize("repo_type", sorted(VALID_REPO_TYPES))
    def test_rescan_broadcasts_and_returns_202(
        self, client, test_db, monkeypatch, repo_type
    ):
        """AC: 202 per valid repo_type, exact UDP payload, no parameters key."""
        device = _seed_device(test_db)
        sent: list = []
        monkeypatch.setattr(settings, "node_listener", "192.168.1.99")
        monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))

        resp = client.post(f"/api/devices/{device.id}/rescan/{repo_type}")

        event = f"system.{repo_type}.get_hash"
        assert resp.status_code == 202
        assert resp.json() == {
            "message": "Rescan broadcast sent",
            "event": event,
            "target": device.node,
        }

        assert len(sent) == 1
        assert sent[0] == {"event": event, "targets": [device.node]}

    def test_invalid_repo_type_returns_400(self, client, monkeypatch):
        """AC: repo_type outside VALID_REPO_TYPES -> 400 (checked first)."""
        sent: list = []
        monkeypatch.setattr(settings, "node_listener", "192.168.1.99")
        monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))

        resp = client.post("/api/devices/1/rescan/firmware")

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid repository type"
        assert sent == []

    def test_unknown_device_returns_404(self, client, monkeypatch):
        """AC: missing device -> 404, nothing broadcast."""
        sent: list = []
        monkeypatch.setattr(settings, "node_listener", "192.168.1.99")
        monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))

        resp = client.post("/api/devices/9999/rescan/userspace")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Device not found"
        assert sent == []

    def test_listener_not_configured_returns_503(
        self, client, test_db, monkeypatch
    ):
        """AC: empty node_listener -> 503, nothing broadcast."""
        device = _seed_device(test_db)
        sent: list = []
        monkeypatch.setattr(settings, "node_listener", "")
        monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))

        resp = client.post(f"/api/devices/{device.id}/rescan/userspace")

        assert resp.status_code == 503
        assert resp.json()["detail"] == "Node listener not configured"
        assert sent == []
