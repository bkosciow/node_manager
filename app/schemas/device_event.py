"""Pydantic schemas for the DeviceEvent resource."""

from datetime import datetime

from pydantic import BaseModel


class DeviceEventResponse(BaseModel):
    id: int
    device_id: int
    event_type: str
    parameters: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceEventsResponse(BaseModel):
    """Dict of event_type → parameters, built manually from query results."""
    pass


class SupportedEventTypes:
    """Constant set of supported event type strings."""
    PONG = "system.pong"
    MICROPLATE_HASH = "system.microplate.hash"
    USERSPACE_HASH = "system.userspace.hash"

    ALL = {PONG, MICROPLATE_HASH, USERSPACE_HASH}
