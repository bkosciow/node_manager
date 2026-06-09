"""Pydantic schemas for the Repository resource."""

from datetime import datetime

from pydantic import BaseModel, field_validator


VALID_REPO_TYPES = ("microplate", "userspace")


class RepositoryFileResponse(BaseModel):
    id: int
    filename: str
    sha256: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepositoryResponse(BaseModel):
    id: int
    name: str
    repo_type: str
    files: list[RepositoryFileResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


class RepositoryCreate(BaseModel):
    name: str
    repo_type: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str:
        if not v or not v.strip():
            raise ValueError("name must be a non-empty string")
        return v.strip()

    @field_validator("repo_type")
    @classmethod
    def validate_repo_type(cls, v: str | None) -> str:
        if not v or not v.strip():
            raise ValueError("repo_type must be a non-empty string")
        value = v.strip().lower()
        if value not in VALID_REPO_TYPES:
            raise ValueError(
                f"repo_type must be one of {list(VALID_REPO_TYPES)}, got '{value}'"
            )
        return value
