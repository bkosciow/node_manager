"""Pydantic schemas for DeviceIgnoredFile."""

from datetime import datetime

from pydantic import BaseModel, field_validator


class IgnoredFileCreate(BaseModel):
    repo_type: str
    filename: str

    @field_validator("repo_type")
    @classmethod
    def validate_repo_type(cls, v: str | None) -> str:
        if v not in ("microplate", "userspace"):
            raise ValueError(f"Invalid repo type: {v}. Must be microplate or userspace")
        return v

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str | None) -> str:
        if not v or not v.strip():
            raise ValueError("filename must be a non-empty string")
        return v.strip()


class IgnoredFileResponse(BaseModel):
    id: int
    device_id: int
    repo_type: str
    filename: str
    ignored_at: datetime

    model_config = {"from_attributes": True}
