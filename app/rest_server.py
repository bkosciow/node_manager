"""FastAPI REST server for IoT Device Discovery Service."""

import logging

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.crud.device import get_device, get_devices
from app.crud.update_status import get_device_updates, get_repo_file_diff
from app.crud.device_event import get_event, get_events
from app.crud.node_repository import assign_repo_to_node, get_assignments
from app.crud.repository import get_repositories
from app.crud.device_ignored_file import (
    create_ignored_file,
    delete_ignored_file,
    get_ignored_files,
)
from app.db.session import get_db, init_db
from app.models.device_ignored_file import DeviceIgnoredFile
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
from app.schemas.repository import VALID_REPO_TYPES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="IoT Device Discovery Service",
    version="0.1.0",
    description="Discovers and deduplicates IoT devices from UDP broadcast messages.",
)


@app.on_event("startup")
def startup() -> None:
    init_db()
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

    from app.crud.repository import get_repository

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


# -- Entry point -------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    from app.config import settings

    uvicorn.run(
        "app.rest_server:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
