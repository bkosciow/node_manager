"""FastAPI REST server for IoT Device Discovery Service."""

import logging

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.crud.device import get_device, get_devices
from app.crud.device_event import get_event, get_events
from app.db.session import get_db, init_db
from app.models.device import Device
from app.schemas.device import DeviceResponse
from app.schemas.device_event import SupportedEventTypes

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


@app.get("/api/devices", response_model=list[DeviceResponse], tags=["devices"])
def list_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> list[Device]:
    return get_devices(db, skip=skip, limit=limit)


@app.get("/api/devices/{device_id}", tags=["devices"])
def get_single_device(
    device_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    """Get device details with logged events."""
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    events = get_events(db, device_id)
    return {
        "id": device.id,
        "chip_id": device.chip_id,
        "node": device.node,
        "created_at": device.created_at.isoformat(),
        "events": {e.event_type: e.parameters for e in events},
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
