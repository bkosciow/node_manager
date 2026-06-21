"""Check whether a device has pending repository updates."""

from app.models.device_event import DeviceEvent
from app.models.node_repository import NodeRepository
from app.models.repository import RepositoryFile

from sqlalchemy.orm import Session, joinedload


def _get_hash_dicts(
    db: Session,
    device_id: int,
    repository_id: int,
    repo_type: str,
) -> tuple[dict | None, dict]:
    """Return ``(device_hashes, repo_hashes)`` dicts keyed by filename.

    ``device_hashes`` is ``None`` when the device has never reported hashes
    for this repo type.
    """
    event_type = f"system.{repo_type}.hash"

    device_event = (
        db.query(DeviceEvent)
        .filter(
            DeviceEvent.device_id == device_id,
            DeviceEvent.event_type == event_type,
        )
        .first()
    )

    device_hashes: dict | None = None
    if device_event is not None:
        device_hashes = device_event.parameters or {}

    repo_files = (
        db.query(RepositoryFile)
        .options(joinedload(RepositoryFile.repository))
        .filter(RepositoryFile.repository_id == repository_id)
        .all()
    )

    repo_hashes = {f.filename: f.sha256 for f in repo_files}

    return device_hashes, repo_hashes


def check_update_available(
    db: Session,
    device_id: int,
    repository_id: int,
    repo_type: str,
) -> bool:
    """Return True if any file hash in the repo differs from the device.

    Edge cases:
    - No event from device yet  -> False  (no hashes to compare)
    - File present on one side only -> True
    """
    device_hashes, repo_hashes = _get_hash_dicts(
        db, device_id, repository_id, repo_type
    )

    if device_hashes is None:
        return False

    return device_hashes != repo_hashes


def get_repo_file_diff(
    db: Session,
    device_id: int,
    repository_id: int,
    repo_type: str,
) -> list[dict]:
    """Return list of files that differ between repo and device.

    Each entry: ``{"filename": str, "device_hash": str | None,
    "repo_hash": str | None}``

    - ``device_hash`` is ``None`` if the file only exists in the repo
    - ``repo_hash`` is ``None`` if the file only exists on the device
    - Empty list when there is no diff or the device has never reported
      hashes.
    """
    device_hashes, repo_hashes = _get_hash_dicts(
        db, device_id, repository_id, repo_type
    )

    if device_hashes is None:
        return []

    all_filenames = set(device_hashes.keys()) | set(repo_hashes.keys())

    diff: list[dict] = []
    for filename in sorted(all_filenames):
        d_hash = device_hashes.get(filename)
        r_hash = repo_hashes.get(filename)
        if d_hash != r_hash:
            diff.append(
                {
                    "filename": filename,
                    "device_hash": d_hash,
                    "repo_hash": r_hash,
                }
            )

    return diff


def get_device_updates(db: Session, device_id: int) -> dict:
    """Return ``{"microplate": bool, "userspace": bool}`` for a device.

    No assignment for a given repo_type -> False (nothing to compare).
    """
    assignments = (
        db.query(NodeRepository)
        .options(joinedload(NodeRepository.repository))
        .filter(NodeRepository.device_id == device_id)
        .all()
    )

    assignment_map = {a.repo_type: a for a in assignments}

    result = {"microplate": False, "userspace": False}

    for repo_type in ("microplate", "userspace"):
        assignment = assignment_map.get(repo_type)
        if assignment is None:
            result[repo_type] = False
        else:
            result[repo_type] = check_update_available(
                db, device_id, assignment.repository_id, repo_type
            )

    return result
