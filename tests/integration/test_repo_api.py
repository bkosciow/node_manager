"""Integration tests for Repository and Assignment REST API endpoints."""

from app.crud.device import create_device
from app.crud.repository import (
    create_repository,
    upsert_repository_file,
)
from app.schemas.device import DeviceCreate
from app.schemas.repository import RepositoryCreate

from tests.conftest import SAMPLE_DEVICE_1


# -- GET /api/repos ----------------------------------------------------------


class TestRepoList:
    def test_no_repos_returns_empty_list(self, client):
        """AC: No repos of type -> 200, empty list []."""
        resp = client.get("/api/repos?type=microplate")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_repos_with_files(self, client, test_db):
        """AC: Repos exist -> 200, list with name, type, files."""
        repo = create_repository(
            test_db, RepositoryCreate(name="node_north", repo_type="microplate")
        )
        test_db.commit()
        upsert_repository_file(test_db, repo.id, "core.py", "a" * 64)
        test_db.commit()

        resp = client.get("/api/repos?type=microplate")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        repo_data = data[0]
        assert repo_data["name"] == "node_north"
        assert repo_data["repo_type"] == "microplate"
        assert "files" in repo_data
        assert len(repo_data["files"]) == 1
        file_data = repo_data["files"][0]
        assert file_data["filename"] == "core.py"
        assert file_data["sha256"] == "a" * 64
        assert "updated_at" in file_data

    def test_invalid_type_returns_400(self, client):
        """AC: Invalid type -> 400 bad request."""
        resp = client.get("/api/repos?type=invalid")
        assert resp.status_code == 400

    def test_microplate_filter(self, client, test_db):
        """AC: type=microplate -> returns only microplate repos."""
        create_repository(
            test_db, RepositoryCreate(name="mp", repo_type="microplate")
        )
        create_repository(
            test_db, RepositoryCreate(name="us", repo_type="userspace")
        )
        test_db.commit()

        resp = client.get("/api/repos?type=microplate")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["repo_type"] == "microplate"

    def test_userspace_filter(self, client, test_db):
        """AC: type=userspace -> returns only userspace repos."""
        create_repository(
            test_db, RepositoryCreate(name="mp", repo_type="microplate")
        )
        create_repository(
            test_db, RepositoryCreate(name="us", repo_type="userspace")
        )
        test_db.commit()

        resp = client.get("/api/repos?type=userspace")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["repo_type"] == "userspace"


# -- POST /api/nodes/{device_id}/repos ---------------------------------------


class TestRepoAssignment:
    def test_valid_assignment(self, client, test_db):
        """AC: Valid assignment -> 200, assignment created."""
        device = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
        repo = create_repository(
            test_db, RepositoryCreate(name="node_north", repo_type="microplate")
        )
        test_db.commit()

        resp = client.post(
            f"/api/nodes/{device.id}/repos", json={"repository_id": repo.id}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_id"] == device.id
        assert data["repository_id"] == repo.id
        assert data["repo_type"] == "microplate"

    def test_replace_existing_assignment(self, client, test_db):
        """AC: Replace existing assignment of same type."""
        device = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
        repo1 = create_repository(
            test_db, RepositoryCreate(name="node_north", repo_type="microplate")
        )
        repo2 = create_repository(
            test_db, RepositoryCreate(name="node_south", repo_type="microplate")
        )
        test_db.commit()

        client.post(
            f"/api/nodes/{device.id}/repos", json={"repository_id": repo1.id}
        )
        resp = client.post(
            f"/api/nodes/{device.id}/repos", json={"repository_id": repo2.id}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["repository_id"] == repo2.id

    def test_nonexistent_device_returns_404(self, client, test_db):
        """AC: Non-existent device -> 404."""
        repo = create_repository(
            test_db, RepositoryCreate(name="node_north", repo_type="microplate")
        )
        test_db.commit()

        resp = client.post(
            "/api/nodes/9999/repos", json={"repository_id": repo.id}
        )
        assert resp.status_code == 404

    def test_nonexistent_repo_returns_404(self, client, test_db):
        """AC: Non-existent repository -> 404."""
        device = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
        test_db.commit()

        resp = client.post(
            f"/api/nodes/{device.id}/repos", json={"repository_id": 9999}
        )
        assert resp.status_code == 404

    def test_assign_second_type(self, client, test_db):
        """AC: Assign second type to same node -> both assignments exist."""
        device = create_device(test_db, DeviceCreate(**SAMPLE_DEVICE_1))
        repo_mp = create_repository(
            test_db, RepositoryCreate(name="mp", repo_type="microplate")
        )
        repo_us = create_repository(
            test_db, RepositoryCreate(name="us", repo_type="userspace")
        )
        test_db.commit()

        client.post(
            f"/api/nodes/{device.id}/repos", json={"repository_id": repo_mp.id}
        )
        resp = client.post(
            f"/api/nodes/{device.id}/repos", json={"repository_id": repo_us.id}
        )
        assert resp.status_code == 200
