"""CRUD operations for Repository and RepositoryFile models."""

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.repository import Repository, RepositoryFile
from app.schemas.repository import RepositoryCreate


def get_repository(db: Session, repo_id: int) -> Repository | None:
    return (
        db.query(Repository)
        .options(joinedload(Repository.files))
        .filter(Repository.id == repo_id)
        .first()
    )


def get_repositories(
    db: Session, repo_type: str
) -> list[Repository]:
    return (
        db.query(Repository)
        .options(joinedload(Repository.files))
        .filter(Repository.repo_type == repo_type)
        .all()
    )


def create_repository(db: Session, data: RepositoryCreate) -> Repository:
    db_obj = Repository(name=data.name, repo_type=data.repo_type)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def upsert_repository_file(
    db: Session, repo_id: int, filename: str, sha256: str
) -> RepositoryFile:
    existing = (
        db.query(RepositoryFile)
        .filter(
            RepositoryFile.repository_id == repo_id,
            RepositoryFile.filename == filename,
        )
        .first()
    )
    if existing is not None:
        existing.sha256 = sha256
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    db_obj = RepositoryFile(
        repository_id=repo_id,
        filename=filename,
        sha256=sha256,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def cleanup_repository_files(
    db: Session, repo_id: int, existing_filenames: set[str]
) -> int:
    deleted = (
        db.query(RepositoryFile)
        .filter(
            RepositoryFile.repository_id == repo_id,
            RepositoryFile.filename.notin_(existing_filenames),
        )
        .delete(synchronize_session="fetch")
    )
    db.commit()
    return deleted
