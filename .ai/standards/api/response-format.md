# Response Format

No response envelope — endpoints return raw data or lists directly.

```python
# List endpoint — response_model on the route
@app.get("/api/devices", response_model=list[DeviceResponse])
def list_devices(...):
    return get_devices(db, skip=skip, limit=limit)

# Detail endpoint — hand-built dict with embedded relationships
@app.get("/api/devices/{device_id}")
def get_single_device(...):
    return {
        "id": device.id,
        "chip_id": device.chip_id,
        "events": {e.event_type: e.parameters for e in events},
        "assigned_repos": [...],
    }
```

- List endpoints: `response_model=list[ResponseSchema]`
- Detail endpoints: hand-built dicts with embedded relationships (events, assignments)
- POST success: return `{"message": "..."}` dict
- Health: plain `{"status": "ok"}` — no auth, no response_model

## Mixed response_model usage

- Some endpoints declare `response_model`; others return `dict`
- Complex nested responses (device details with events + repos) are built inline
- Long-term goal: consistent `response_model` on all endpoints
