"""CRUD operations for NodeRepository (repo-to-node assignments)."""

from sqlalchemy.orm import Session

from app.models.node_repository import NodeRepository
from app.models.repository import Repository


def assign_repo_to_node(
    db: Session, device_id: int, repository_id: int, repo_type: str
) -> NodeRepository | None:
    """Assign a repo to a node, replacing existing assignment of same type.

    Returns None if device or repository doesn't exist.
    """
    from app.models.device import Device

    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        return None

    repository = db.query(Repository).filter(
        Repository.id == repository_id
    ).first()
    if repository is None:
        return None

    # Delete existing assignment of the same type
    db.query(NodeRepository).filter(
        NodeRepository.device_id == device_id,
        NodeRepository.repo_type == repo_type,
    ).delete()

    # Create new assignment
    assignment = NodeRepository(
        device_id=device_id,
        repository_id=repository_id,
        repo_type=repo_type,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_assignments(db: Session, device_id: int) -> list[NodeRepository]:
    """Get all repo assignments for a device."""
    return (
        db.query(NodeRepository)
        .filter(NodeRepository.device_id == device_id)
        .all()
    )
