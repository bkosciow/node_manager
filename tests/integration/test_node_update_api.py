"""Integration tests for the node update (upgrade) REST endpoints."""

from app.config import settings
from app.crud.device import create_device
from app.crud.node_repository import assign_repo_to_node
from app.crud.node_update import create_node_update, get_node_update_by_token
from app.crud.repository import create_repository, upsert_repository_file
from app.models.device_event import DeviceEvent
from app.schemas.device import DeviceCreate
from app.schemas.node_update import NodeUpdateCreate
from app.schemas.repository import RepositoryCreate
from app.services import comm

from tests.conftest import SAMPLE_DEVICE_1

# config.py differs (a vs b), main.py matches, stray.txt is device-only.
# The trigger must broadcast only ["config.py"].
REPO_FILES = [("config.py", "b" * 64), ("main.py", "c" * 64)]
DEVICE_HASHES = {
    "config.py": "a" * 64,
    "main.py": "c" * 64,
    "stray.txt": "e" * 64,
}


def _seed_upgrade_scenario(test_db):
    """Device + userspace repo with a one-file diff. Returns (device, repo)."""
    device = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
    repo = create_repository(
        test_db, RepositoryCreate(name="node_north", repo_type="userspace")
    )
    for filename, digest in REPO_FILES:
        upsert_repository_file(test_db, repo.id, filename, digest)
    test_db.add(
        DeviceEvent(
            device_id=device.id,
            event_type="system.userspace.hash",
            parameters=DEVICE_HASHES,
        )
    )
    test_db.commit()
    assign_repo_to_node(test_db, device.id, repo.id, "userspace")
    return device, repo


def _seed_device_only_diff(test_db):
    """Repo hashes all match; device has one extra file -> empty diff.

    Returns (device, repo).
    """
    device = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
    repo = create_repository(
        test_db, RepositoryCreate(name="node_north", repo_type="userspace")
    )
    matching = {name: digest for name, digest in REPO_FILES}
    for filename, digest in REPO_FILES:
        upsert_repository_file(test_db, repo.id, filename, digest)
    test_db.add(
        DeviceEvent(
            device_id=device.id,
            event_type="system.userspace.hash",
            parameters={**matching, "stray.txt": "e" * 64},
        )
    )
    test_db.commit()
    assign_repo_to_node(test_db, device.id, repo.id, "userspace")
    return device, repo


def _trigger(device, client, monkeypatch) -> str:
    """Trigger an upgrade for a seeded device; return the session token."""
    sent: list = []
    monkeypatch.setattr(settings, "node_listener", "192.168.1.99")
    monkeypatch.setattr(settings, "base_url", "http://nm.example.com")
    monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))
    resp = client.post(f"/api/devices/{device.id}/update/userspace")
    assert resp.status_code == 202
    return resp.json()["token"]


# -- POST /api/devices/{device_id}/update/{repo_type} ------------------------


class TestTriggerDeviceUpdate:
    def test_trigger_broadcasts_and_creates_session(
        self, client, test_db, monkeypatch
    ):
        """AC: 202, filtered diff broadcast, session row created."""
        device, _repo = _seed_upgrade_scenario(test_db)
        sent: list = []
        monkeypatch.setattr(settings, "node_listener", "192.168.1.99")
        monkeypatch.setattr(settings, "base_url", "http://nm.example.com")
        monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))

        resp = client.post(f"/api/devices/{device.id}/update/userspace")

        assert resp.status_code == 202
        data = resp.json()
        assert data["message"] == "Upgrade broadcast sent"
        assert data["files"] == ["config.py"]
        token = data["token"]

        assert len(sent) == 1
        payload = sent[0]
        assert payload["event"] == "system.files.upgrade"
        assert payload["targets"] == [device.node]
        assert payload["parameters"]["type"] == "userspace"
        assert payload["parameters"]["files"] == ["config.py"]
        assert (
            payload["parameters"]["base_url"]
            == f"http://nm.example.com/api/update/{token}"
        )

        session = get_node_update_by_token(test_db, token)
        assert session is not None
        assert session.files == ["config.py"]
        assert session.fetched_files == []
        assert session.validated_files == []

    def test_invalid_repo_type_returns_400(self, client):
        """AC: repo_type outside VALID_REPO_TYPES -> 400."""
        resp = client.post("/api/devices/1/update/firmware")
        assert resp.status_code == 400

    def test_unknown_device_returns_404(self, client):
        """AC: missing device -> 404."""
        resp = client.post("/api/devices/9999/update/userspace")
        assert resp.status_code == 404

    def test_no_assignment_returns_404(self, client, test_db):
        """AC: device without a userspace repo -> 404 assignment error."""
        device = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))

        resp = client.post(f"/api/devices/{device.id}/update/userspace")

        assert resp.status_code == 404
        assert "No userspace repository assigned" in resp.json()["detail"]

    def test_device_only_diff_returns_404(self, client, test_db):
        """AC: diff with only device-side entries -> nothing to update.

        Device-only entries (repo_hash None) are excluded from the
        broadcast, so a diff containing none of the repo's files must
        yield a 404 instead of a 404-loop for the node.
        """
        device, _repo = _seed_device_only_diff(test_db)

        resp = client.post(f"/api/devices/{device.id}/update/userspace")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Nothing to update"

    def test_listener_not_configured_returns_503(self, client, test_db, monkeypatch):
        """AC: empty node_listener -> 503, no session created."""
        device, _repo = _seed_upgrade_scenario(test_db)
        monkeypatch.setattr(settings, "node_listener", "")

        resp = client.post(f"/api/devices/{device.id}/update/userspace")

        assert resp.status_code == 503
        assert resp.json()["detail"] == "Node listener not configured"


# -- GET /api/update/{token}/get/{filename} ----------------------------------


class TestServeUpgradeFile:
    def test_serves_file_and_records_fetch(
        self, client, test_db, monkeypatch, tmp_path
    ):
        """AC: 200 file body, fetched_files recorded."""
        device, _repo = _seed_upgrade_scenario(test_db)
        upgrade_dir = tmp_path / "node_north" / "_userspace"
        upgrade_dir.mkdir(parents=True)
        (upgrade_dir / "config.py").write_text("print('new')\n")
        monkeypatch.setattr(settings, "upgrades_dir", str(tmp_path))
        token = _trigger(device, client, monkeypatch)

        resp = client.get(f"/api/update/{token}/get/config.py")

        assert resp.status_code == 200
        assert b"print('new')" in resp.content

        session = get_node_update_by_token(test_db, token)
        assert session.fetched_files == ["config.py"]

    def test_unknown_token_returns_404(self, client):
        """AC: unknown token -> 404."""
        resp = client.get("/api/update/deadbeef/get/config.py")
        assert resp.status_code == 404

    def test_filename_not_in_session_returns_404(
        self, client, test_db, monkeypatch
    ):
        """AC: filename outside the session's files allow-list -> 404.

        main.py is not in the filtered diff, so it must be rejected
        even though a RepositoryFile record for it exists.
        """
        device, _repo = _seed_upgrade_scenario(test_db)
        token = _trigger(device, client, monkeypatch)

        resp = client.get(f"/api/update/{token}/get/main.py")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "File not part of this upgrade"

    def test_missing_repo_file_record_returns_404(
        self, client, test_db, monkeypatch, tmp_path
    ):
        """AC: no RepositoryFile row for the filename -> 404."""
        device = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
        repo = create_repository(
            test_db, RepositoryCreate(name="node_north", repo_type="userspace")
        )
        create_node_update(
            test_db,
            NodeUpdateCreate(
                token="tok-ghost",
                device_id=device.id,
                repository_id=repo.id,
                repo_type="userspace",
                files=["ghost.py"],
            ),
        )
        upgrade_dir = tmp_path / "node_north" / "_userspace"
        upgrade_dir.mkdir(parents=True)
        (upgrade_dir / "ghost.py").write_text("x")
        monkeypatch.setattr(settings, "upgrades_dir", str(tmp_path))

        resp = client.get("/api/update/tok-ghost/get/ghost.py")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "File not found"

    def test_missing_on_disk_returns_404(
        self, client, test_db, monkeypatch, tmp_path
    ):
        """AC: file absent under upgrades_dir -> 404."""
        device, _repo = _seed_upgrade_scenario(test_db)
        (tmp_path / "node_north" / "_userspace").mkdir(parents=True)
        monkeypatch.setattr(settings, "upgrades_dir", str(tmp_path))
        token = _trigger(device, client, monkeypatch)

        resp = client.get(f"/api/update/{token}/get/config.py")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "File not found"


# -- POST /api/update/{token}/validate/{filename} ----------------------------


class TestValidateUpgradeFile:
    def test_valid_hash(self, client, test_db, monkeypatch):
        """AC: matching hash -> 200 {"valid": true}, recorded."""
        device, _repo = _seed_upgrade_scenario(test_db)
        token = _trigger(device, client, monkeypatch)

        resp = client.post(
            f"/api/update/{token}/validate/config.py", json={"hash": "b" * 64}
        )

        assert resp.status_code == 200
        assert resp.json() == {"valid": True}

        session = get_node_update_by_token(test_db, token)
        assert session.validated_files == ["config.py"]

    def test_hash_mismatch_returns_400(self, client, test_db, monkeypatch):
        """AC: mismatch -> 400 with received/expected hashes."""
        device, _repo = _seed_upgrade_scenario(test_db)
        token = _trigger(device, client, monkeypatch)

        resp = client.post(
            f"/api/update/{token}/validate/config.py", json={"hash": "z" * 64}
        )

        assert resp.status_code == 400
        data = resp.json()
        assert data["valid"] is False
        assert data["received_hash"] == "z" * 64
        assert data["expected_hash"] == "b" * 64

    def test_unknown_token_returns_404(self, client):
        """AC: unknown token -> 404."""
        resp = client.post(
            "/api/update/deadbeef/validate/config.py", json={"hash": "x" * 64}
        )
        assert resp.status_code == 404

    def test_filename_not_in_session_returns_404(
        self, client, test_db, monkeypatch
    ):
        """AC: filename outside the session's files allow-list -> 404."""
        device, _repo = _seed_upgrade_scenario(test_db)
        token = _trigger(device, client, monkeypatch)

        resp = client.post(
            f"/api/update/{token}/validate/main.py", json={"hash": "c" * 64}
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "File not part of this upgrade"

    def test_missing_hash_record_returns_404(self, client, test_db, monkeypatch):
        """AC: no RepositoryFile row for the filename -> 404."""
        device = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
        repo = create_repository(
            test_db, RepositoryCreate(name="node_north", repo_type="userspace")
        )
        create_node_update(
            test_db,
            NodeUpdateCreate(
                token="tok-ghost",
                device_id=device.id,
                repository_id=repo.id,
                repo_type="userspace",
                files=["ghost.py"],
            ),
        )

        resp = client.post(
            "/api/update/tok-ghost/validate/ghost.py", json={"hash": "x" * 64}
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Hash not found"


# -- GET /api/devices/{device_id}/updates ------------------------------------


class TestListDeviceUpdates:
    def test_lists_sessions_newest_first(self, client, test_db, monkeypatch):
        """AC: sessions for the device, newest first."""
        device, _repo = _seed_upgrade_scenario(test_db)
        token1 = _trigger(device, client, monkeypatch)
        token2 = _trigger(device, client, monkeypatch)

        resp = client.get(f"/api/devices/{device.id}/updates")

        assert resp.status_code == 200
        rows = resp.json()
        assert [r["token"] for r in rows] == [token2, token1]
        assert all(r["fetched_files"] == [] for r in rows)
        assert all(r["repo_type"] == "userspace" for r in rows)

    def test_unknown_device_returns_404(self, client):
        """AC: missing device -> 404."""
        resp = client.get("/api/devices/9999/updates")
        assert resp.status_code == 404
