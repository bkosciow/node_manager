"""Pydantic schemas for NodeUpdate upgrade sessions."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.repository import VALID_REPO_TYPES


class NodeUpdateCreate(BaseModel):
    token: str
    device_id: int
    repository_id: int
    repo_type: str
    files: list[str]

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

    @field_validator("files")
    @classmethod
    def validate_files(cls, v: list[str] | None) -> list[str]:
        if not v:
            raise ValueError("files must not be empty")
        return v


class NodeUpdateResponse(BaseModel):
    id: int
    token: str
    device_id: int
    repository_id: int
    repo_type: str
    files: list[str]
    fetched_files: list[str]
    validated_files: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UpdateValidateRequest(BaseModel):
    hash: str
