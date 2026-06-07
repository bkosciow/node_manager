"""Pydantic schemas for the Device resource."""

from datetime import datetime

from pydantic import BaseModel, field_validator


class DeviceCreate(BaseModel):
    chip_id: str
    node: str

    @field_validator("chip_id")
    @classmethod
    def validate_chip_id(cls, v: str | None) -> str:
        if not v or not v.strip():
            raise ValueError("chip_id must be a non-empty string")
        return v.strip()

    @field_validator("node")
    @classmethod
    def validate_node(cls, v: str | None) -> str:
        if not v or not v.strip():
            raise ValueError("node must be a non-empty string")
        return v.strip()


class DeviceResponse(BaseModel):
    id: int
    chip_id: str
    node: str
    created_at: datetime

    model_config = {"from_attributes": True}
