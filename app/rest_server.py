"""FastAPI REST server for IoT Device Discovery Service."""

import logging
import os
import uuid

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.config import settings
from app.crud.device import get_device, get_devices
from app.crud.update_status import get_device_updates, get_repo_file_diff
from app.crud.device_event import get_event, get_events
from app.crud.node_repository import assign_repo_to_node, get_assignments
from app.crud.node_update import (
    create_node_update,
    get_node_update_by_token,
    list_node_updates,
    record_fetched_file,
    record_validated_file,
)
from app.crud.repository import get_repositories, get_repository
from app.crud.device_ignored_file import (
    create_ignored_file,
    delete_ignored_file,
    get_ignored_files,
)
from app.db.migrate import run_migrations
from app.db.session import get_db
from app.models.device_ignored_file import DeviceIgnoredFile
from app.models.repository import RepositoryFile
from app.schemas.device import DeviceWithUpdates, UpdatesAvailable
from app.schemas.device_event import SupportedEventTypes
from app.schemas.device_ignored_file import (
    IgnoredFileCreate,
    IgnoredFileResponse,
)
from app.schemas.node_repository import (
    RepoAssignmentCreate,
    RepoAssignmentResponse,
)
from app.schemas.node_update import (
    NodeUpdateCreate,
    NodeUpdateResponse,
    UpdateValidateRequest,
)
from app.schemas.repository import VALID_REPO_TYPES, RepoRescanResponse
from app.services import comm
from app.services.iot_bootstrap import bootstrap
from app.services.repo_scan import (
    list_repo_files_on_disk,
    scan_repo,
    start_auto_scan,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="IoT Device Discovery Service",
    version="0.1.0",
    description="Discovers and deduplicates IoT devices from UDP broadcast messages.",
)


@app.on_event("startup")
def startup() -> None:
    run_migrations()
    if settings.node_listener:
        bootstrap(
            send_to=(settings.node_listener, int(settings.node_listener_port))
        )
    else:
        bootstrap()
    start_auto_scan(settings.repo_scan_interval_minutes)
    logger.info("REST server startup complete")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# -- Device endpoints --------------------------------------------------------


@app.get("/api/devices", response_model=list[DeviceWithUpdates], tags=["devices"])
def list_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> list[DeviceWithUpdates]:
    devices = get_devices(db, skip=skip, limit=limit)
    return [
        DeviceWithUpdates(
            id=device.id,
            chip_id=device.chip_id,
            node=device.node,
            created_at=device.created_at,
            last_seen_at=device.last_seen_at,
            last_updated_at=device.last_updated_at,
            updates_available=UpdatesAvailable(**get_device_updates(db, device.id)),
        )
        for device in devices
    ]


@app.get("/api/devices/{device_id}", tags=["devices"])
def get_single_device(
    device_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    """Get device details with logged events and assigned repos."""
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    events = get_events(db, device_id)
    assignments = get_assignments(db, device_id)
    return {
        "id": device.id,
        "chip_id": device.chip_id,
        "node": device.node,
        "created_at": device.created_at.isoformat(),
        "last_seen_at": device.last_seen_at.isoformat(),
        "last_updated_at": (
            device.last_updated_at.isoformat() if device.last_updated_at
            else None
        ),
        "events": {e.event_type: e.parameters for e in events},
        "assigned_repos": [
            {
                "id": a.id,
                "repository_id": a.repository_id,
                "repository_name": a.repository.name,
                "repo_type": a.repo_type,
                "assigned_at": a.assigned_at.isoformat(),
                "updatable_files": get_repo_file_diff(
                    db, device_id, a.repository_id, a.repo_type
                ),
            }
            for a in assignments
        ],
    }


# -- Event endpoints ---------------------------------------------------------


@app.get("/api/devices/{device_id}/events/{event_type}", tags=["device-events"])
def get_device_event(
    device_id: int = Path(ge=1),
    event_type: str = Path(),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    """Get the latest parameters for a specific event type."""
    if event_type not in SupportedEventTypes.ALL:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported event type: {event_type}",
        )
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    event = get_event(db, device_id, event_type)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event.parameters


@app.get("/api/devices/{device_id}/events", tags=["device-events"])
def get_device_events(
    device_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict[str, dict]:
    """Get all event data for a device, keyed by event type."""
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    events = get_events(db, device_id)
    return {e.event_type: e.parameters for e in events}


# -- Ignored files endpoints -------------------------------------------------


@app.get(
    "/api/devices/{device_id}/ignored-files",
    response_model=list[IgnoredFileResponse],
    tags=["ignored-files"],
)
def list_ignored_files(
    device_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> list[DeviceIgnoredFile]:
    """List ignored files for a device."""
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return get_ignored_files(db, device_id)


@app.post(
    "/api/devices/{device_id}/ignored-files",
    response_model=IgnoredFileResponse,
    tags=["ignored-files"],
)
def add_ignored_file(
    device_id: int = Path(ge=1),
    body: IgnoredFileCreate = ...,
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> DeviceIgnoredFile:
    """Add an ignored file for a device."""
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    try:
        ignored = create_ignored_file(db, device_id, body)
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(
                status_code=409,
                detail=f"File '{body.filename}' is already ignored for {body.repo_type}",
            )
        raise
    if ignored is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return ignored


@app.delete(
    "/api/devices/{device_id}/ignored-files",
    tags=["ignored-files"],
)
def remove_ignored_file(
    device_id: int = Path(ge=1),
    repo_type: str = Query(),
    filename: str = Query(),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    """Remove an ignored file for a device."""
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    deleted = delete_ignored_file(db, device_id, repo_type, filename)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Ignored file '{filename}' not found for {repo_type}",
        )
    return {"message": f"File '{filename}' removed from ignored list"}


# -- Repo endpoints ----------------------------------------------------------


@app.get("/api/repos", tags=["repos"])
def list_repos(
    repo_type: str = Query(alias="type"),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> list[dict]:
    """List repositories by type with their files."""
    if repo_type not in VALID_REPO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid repo type: {repo_type}. Must be one of {list(VALID_REPO_TYPES)}",
        )
    repos = get_repositories(db, repo_type=repo_type)
    return [
        {
            "id": repo.id,
            "name": repo.name,
            "repo_type": repo.repo_type,
            "created_at": repo.created_at.isoformat(),
            "files": [
                {
                    "id": f.id,
                    "filename": f.filename,
                    "sha256": f.sha256,
                    "updated_at": f.updated_at.isoformat(),
                }
                for f in repo.files
            ],
        }
        for repo in repos
    ]


@app.post(
    "/api/repos/{repo_id}/rescan",
    response_model=RepoRescanResponse,
    tags=["repos"],
)
def rescan_repository(
    repo_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    """Re-hash this repo's on-disk files and sync the DB records."""
    repo = get_repository(db, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    filenames = list_repo_files_on_disk(repo.name, repo.repo_type)
    if not filenames:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No files found on disk for repository "
                f"{repo.name} ({repo.repo_type})"
            ),
        )
    report = scan_repo(db, repo.name, repo.repo_type, filenames)
    return {
        "repo_name": report.repo_name,
        "repo_type": report.repo_type,
        "files_found": report.files_found,
        "files_added": report.files_added,
        "files_updated": report.files_updated,
        "files_unchanged": report.files_unchanged,
        "files_removed": report.files_removed,
        "errors": report.errors,
    }


# -- Assignment endpoints ----------------------------------------------------


@app.post(
    "/api/nodes/{device_id}/repos",
    response_model=RepoAssignmentResponse,
    tags=["assignments"],
)
def assign_repo(
    device_id: int = Path(ge=1),
    body: RepoAssignmentCreate = ...,
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    """Assign a repository to a node."""
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    repo = get_repository(db, body.repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    assignment = assign_repo_to_node(
        db, device_id, body.repository_id, repo.repo_type
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment failed")
    return {
        "id": assignment.id,
        "device_id": assignment.device_id,
        "repository_id": assignment.repository_id,
        "repo_type": assignment.repo_type,
        "assigned_at": assignment.assigned_at.isoformat(),
    }


# -- Device update (upgrade) endpoints ---------------------------------------


@app.post(
    "/api/devices/{device_id}/update/{repo_type}",
    status_code=202,
    tags=["device-updates"],
)
def trigger_device_update(
    device_id: int = Path(ge=1),
    repo_type: str = Path(),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    """Broadcast a system.files.upgrade message for the repo-side diff."""
    if repo_type not in VALID_REPO_TYPES:
        raise HTTPException(status_code=400, detail="Invalid repository type")

    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    assignments = get_assignments(db, device_id)
    assignment = next(
        (a for a in assignments if a.repo_type == repo_type), None
    )
    if assignment is None:
        raise HTTPException(
            status_code=404,
            detail=f"No {repo_type} repository assigned to this device",
        )

    diff = get_repo_file_diff(db, device_id, assignment.repository_id, repo_type)
    files = [f["filename"] for f in diff if f["repo_hash"] is not None]
    if not files:
        raise HTTPException(status_code=404, detail="Nothing to update")

    if not settings.node_listener:
        raise HTTPException(
            status_code=503, detail="Node listener not configured"
        )

    upgrade_token = str(uuid.uuid4())
    create_node_update(
        db,
        NodeUpdateCreate(
            token=upgrade_token,
            device_id=device_id,
            repository_id=assignment.repository_id,
            repo_type=repo_type,
            files=files,
        ),
    )

    base_url = (
        settings.base_url
        or f"http://{settings.app_host}:{settings.app_port}"
    )
    comm.send(
        {
            "event": "system.files.upgrade",
            "targets": [device.node],
            "parameters": {
                "type": repo_type,
                "files": files,
                "base_url": f"{base_url}/api/update/{upgrade_token}",
            },
        }
    )
    return {
        "message": "Upgrade broadcast sent",
        "token": upgrade_token,
        "files": files,
    }


# Exception: public without verify_token — nodes have no API token;
# scoping via unguessable uuid token + the session's files allow-list.
# Deviates from api/auth ("never bypass verify_token without explicit reason").
@app.get("/api/update/{token}/get/{filename}", tags=["device-updates"])
def serve_upgrade_file(
    token: str = Path(),
    filename: str = Path(),
    db: Session = Depends(get_db),
):
    """Serve an upgrade file to the node. Public: uuid-scoped, no API token."""
    session = get_node_update_by_token(db, token)
    if session is None:
        raise HTTPException(status_code=404, detail="Upgrade not found")
    if filename not in session.files:
        raise HTTPException(status_code=404, detail="File not part of this upgrade")

    repo = get_repository(db, session.repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Upgrade not found")

    repo_file = db.execute(
        select(RepositoryFile).where(
            RepositoryFile.repository_id == repo.id,
            RepositoryFile.filename == filename,
        )
    ).scalar_one_or_none()
    if repo_file is None:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = os.path.join(
        settings.upgrades_dir, repo.name, f"_{session.repo_type}", filename
    )
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    record_fetched_file(db, token, filename)
    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


# Exception: public without verify_token — nodes have no API token;
# scoping via unguessable uuid token + the session's files allow-list.
# Deviates from api/auth ("never bypass verify_token without explicit reason").
@app.post("/api/update/{token}/validate/{filename}", tags=["device-updates"])
def validate_upgrade_file(
    token: str = Path(),
    filename: str = Path(),
    body: UpdateValidateRequest = ...,
    db: Session = Depends(get_db),
):
    """Validate a downloaded file hash. Public: uuid-scoped, no API token."""
    session = get_node_update_by_token(db, token)
    if session is None:
        raise HTTPException(status_code=404, detail="Upgrade not found")
    if filename not in session.files:
        raise HTTPException(status_code=404, detail="File not part of this upgrade")

    repo_file = db.execute(
        select(RepositoryFile).where(
            RepositoryFile.repository_id == session.repository_id,
            RepositoryFile.filename == filename,
        )
    ).scalar_one_or_none()
    if repo_file is None:
        raise HTTPException(status_code=404, detail="Hash not found")

    if body.hash == repo_file.sha256:
        record_validated_file(db, token, filename)
        return {"valid": True}

    return JSONResponse(
        status_code=400,
        content={
            "valid": False,
            "received_hash": body.hash,
            "expected_hash": repo_file.sha256,
        },
    )


@app.get(
    "/api/devices/{device_id}/updates",
    response_model=list[NodeUpdateResponse],
    tags=["device-updates"],
)
def list_device_updates(
    device_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> list[NodeUpdateResponse]:
    """List upgrade sessions for a device, newest first."""
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return list_node_updates(db, device_id)


# -- Device active query endpoints --------------------------------------------


@app.post(
    "/api/devices/{device_id}/ping",
    status_code=202,
    tags=["device-queries"],
)
def ping_device(
    device_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    """Broadcast a system.ping message; the node replies with system.pong."""
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    if not settings.node_listener:
        raise HTTPException(
            status_code=503, detail="Node listener not configured"
        )

    comm.send({"event": "system.ping", "targets": [device.node]})
    return {
        "message": "Ping broadcast sent",
        "event": "system.ping",
        "target": device.node,
    }


@app.post(
    "/api/devices/{device_id}/rescan/{repo_type}",
    status_code=202,
    tags=["device-queries"],
)
def rescan_device(
    device_id: int = Path(ge=1),
    repo_type: str = Path(),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    """Broadcast a system.{repo_type}.get_hash message for a fresh hash report."""
    if repo_type not in VALID_REPO_TYPES:
        raise HTTPException(status_code=400, detail="Invalid repository type")

    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    if not settings.node_listener:
        raise HTTPException(
            status_code=503, detail="Node listener not configured"
        )

    event = f"system.{repo_type}.get_hash"
    comm.send({"event": event, "targets": [device.node]})
    return {
        "message": "Rescan broadcast sent",
        "event": event,
        "target": device.node,
    }


# -- Entry point -------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.rest_server:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
