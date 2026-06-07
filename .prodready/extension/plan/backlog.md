# Implementation Backlog — Event Data Extension

## Sprint 4: Event Data Layer

---

### TASK-012: DeviceEvent SQLAlchemy Model
**Priority**: P0 | **Estimate**: 1h | **Status**: Ready

**Description**:
Create the `DeviceEvent` SQLAlchemy model with `device_id` (FK), `event_type` (String), `parameters` (JSON), `updated_at` (DateTime). Add composite unique constraint on `(device_id, event_type)`. Register in `app/models/__init__.py`.

**Acceptance Criteria**:
- [ ] `DeviceEvent` model in `app/models/device_event.py` with `Mapped[]` + `mapped_column()` pattern
- [ ] Columns: `id` (PK), `device_id` (FK → devices.id, ON DELETE CASCADE), `event_type` (String(100), not null), `parameters` (JSON, not null), `updated_at` (DateTime, default=datetime.utcnow)
- [ ] Composite unique constraint: `UniqueConstraint("device_id", "event_type", name="uq_device_event_type")`
- [ ] Relationship: `device` → `Device` via `relationship()` with `back_populates`
- [ ] Add `events` relationship to existing `Device` model (`back_populates="device_event"`)
- [ ] Model registered in `app/models/__init__.py`
- [ ] `init_db()` creates the table (via `create_all`)

**Blocked by**: None
**Blocks**: TASK-013, TASK-014

---

### TASK-013: DeviceEvent Pydantic Schemas
**Priority**: P0 | **Estimate**: 0.5h | **Status**: Ready

**Description**:
Create Pydantic schemas for DeviceEvent API responses: `EventParameters` (raw JSON dict), `DeviceEventResponse` (full record), `DeviceEventsResponse` (dict keyed by event_type).

**Acceptance Criteria**:
- [ ] `DeviceEventResponse` schema with `id: int`, `device_id: int`, `event_type: str`, `parameters: dict`, `updated_at: datetime`
- [ ] `DeviceEventsResponse` schema — dict of event_type → parameters
- [ ] Schemas in `app/schemas/device_event.py`
- [ ] Module importable

**Blocked by**: TASK-012
**Blocks**: TASK-017, TASK-018

---

### TASK-014: DeviceEvent CRUD — Upsert, Get, GetOrCreateDevice
**Priority**: P0 | **Estimate**: 2h | **Status**: Ready

**Description**:
Implement CRUD functions: `upsert_event(db, device_id, event_type, parameters)` using `insert().on_duplicate_key_update()`, `get_event(db, device_id, event_type)`, `get_events(db, device_id)`, and `get_or_create_device(db, chip_id, node)` helper.

**Acceptance Criteria**:
- [ ] `upsert_event(db, device_id, event_type, parameters)` — inserts or updates `parameters` + `updated_at` on duplicate key
- [ ] `get_event(db, device_id, event_type)` → `Optional[DeviceEvent]`
- [ ] `get_events(db, device_id)` → `list[DeviceEvent]`
- [ ] `get_or_create_device(db, chip_id, node)` → `Device` — returns existing or creates new (handles IntegrityError)
- [ ] All functions in `app/crud/device_event.py`, re-exported from `app/crud/__init__.py`
- [ ] Follow coding standards: `Mapped` types, proper session handling, `logger.getLogger(__name__)`

**Blocked by**: TASK-012
**Blocks**: TASK-016

---

## Sprint 5: Event Handler Integration

---

### TASK-015: Extend MessageHandler — Event Detection & Tagged Queue
**Priority**: P0 | **Estimate**: 1.5h | **Status**: Ready

**Description**:
Extend `MessageHandler.handle()` to detect supported event types (`system.pong`, `system.microplate.hash`, `system.userspace.hash`) in `message.data['event']`. Queue tagged items: `("device", chip_id, node)` for discovery and `("event", chip_id, node, event_type, parameters)` for events. A single message can produce both a device tuple and an event tuple.

**Acceptance Criteria**:
- [ ] `handle()` checks `data.get('event')` after extracting chip_id and node
- [ ] Supported event types: `system.pong`, `system.microplate.hash`, `system.userspace.hash` (constant set)
- [ ] On supported event: queue `("event", chip_id, node, event_type, parameters)` — parameters = `data.get('parameters', {})`
- [ ] Device discovery tuple still queued as `("device", chip_id, node)` (backwards compatible)
- [ ] Unrecognized event: only device tuple queued (no event tuple)
- [ ] Missing `parameters` key: default to empty dict `{}`
- [ ] Queue type annotation updated to reflect tagged tuples
- [ ] No regression — existing device discovery path unchanged

**Blocked by**: None
**Blocks**: TASK-016

---

### TASK-016: Extend Worker — Dispatch & Event Upsert
**Priority**: P0 | **Estimate**: 2h | **Status**: Ready

**Description**:
Extend the worker loop to dispatch on tag. For `"device"` items, call existing `_process()`. For `"event"` items, call new `_process_event()` which: (1) gets or creates device, (2) upserts DeviceEvent, (3) handles errors gracefully.

**Acceptance Criteria**:
- [ ] Worker loop unpacks tagged tuples: `("device", ...)` or `("event", ...)`
- [ ] `"device"` tag → existing `_process(chip_id, node, ...)` path
- [ ] `"event"` tag → new `_process_event(chip_id, node, event_type, parameters, ...)`
- [ ] `_process_event()`: calls `get_or_create_device()`, then `upsert_event()`
- [ ] Each event uses its own DB session (create from `SessionLocal`, close in `finally`)
- [ ] `IntegrityError` on device auto-create: log warning, skip event (no crash)
- [ ] Any DB error in `_process_event()`: log error, continue worker loop
- [ ] No regression — existing device processing unchanged

**Blocked by**: TASK-014, TASK-015
**Blocks**: None

---

## Sprint 6: Event API

---

### TASK-017: GET /api/devices/{device_id}/events/{event_type}
**Priority**: P0 | **Estimate**: 1h | **Status**: Ready

**Description**:
Add endpoint to retrieve the latest parameters for a specific event type for a device. Returns 404 if device missing or event not found, 400 if event type is unsupported.

**Acceptance Criteria**:
- [ ] `GET /api/devices/{device_id}/events/{event_type}` returns parameters dict as JSON
- [ ] `device_id: int` path param with `ge=1`
- [ ] `event_type: str` path param — validated against supported types set
- [ ] 404 if device not found: `HTTPException(status_code=404, detail="Device not found")`
- [ ] 404 if event type not stored for device: `HTTPException(status_code=404, detail="Event not found")`
- [ ] 400 if unsupported event type: `HTTPException(status_code=400, detail="Unsupported event type")`
- [ ] Auth: `token: str = Depends(verify_token)`
- [ ] `tags=["device-events"]`
- [ ] Follow coding standards

**Blocked by**: TASK-013, TASK-014
**Blocks**: None

---

### TASK-018: GET /api/devices/{device_id}/events
**Priority**: P1 | **Estimate**: 0.5h | **Status**: Ready

**Description**:
Add endpoint to retrieve all stored event types for a device as a JSON object keyed by event_type.

**Acceptance Criteria**:
- [ ] `GET /api/devices/{device_id}/events` returns `{event_type: parameters, ...}`
- [ ] 404 if device not found
- [ ] Returns `{}` if device has no stored events
- [ ] Auth: `token: str = Depends(verify_token)`
- [ ] `tags=["device-events"]`
- [ ] Follow coding standards

**Blocked by**: TASK-017
**Blocks**: None

---

## Sprint 7: Tests

---

### TASK-019: Unit Tests — Event Handler & CRUD
**Priority**: P1 | **Estimate**: 2h | **Status**: Ready

**Description**:
Unit tests for event routing in MessageHandler, DeviceEvent CRUD (upsert, get, get_or_create_device).

**Acceptance Criteria**:
- [ ] Test: message with `system.pong` event → event tuple queued with correct tag
- [ ] Test: message with `system.microplate.hash` → event tuple queued
- [ ] Test: message with `system.userspace.hash` → event tuple queued
- [ ] Test: message with unrecognized event → only device tuple queued
- [ ] Test: message with no event field → only device tuple queued
- [ ] Test: worker dispatch `"device"` tag → `_process` called
- [ ] Test: worker dispatch `"event"` tag → `_process_event` called
- [ ] Test: `upsert_event` — insert new record
- [ ] Test: `upsert_event` — update existing record (parameters + updated_at changed)
- [ ] Test: `get_event` — returns record for matching device_id + event_type
- [ ] Test: `get_event` — returns None for missing event_type
- [ ] Test: `get_events` — returns all events for device
- [ ] Test: `get_or_create_device` — returns existing device
- [ ] Test: `get_or_create_device` — creates new device if not found
- [ ] Test: `_process_event` — IntegrityError on device create → logged, no crash
- [ ] Tests in `tests/unit/test_event_handler.py` and `tests/unit/test_event_crud.py`
- [ ] Use SQLite in-memory for CRUD tests, mocks for handler tests

**Blocked by**: TASK-016, TASK-014
**Blocks**: None

---

### TASK-020: Integration Tests — Event API Endpoints
**Priority**: P1 | **Estimate**: 1.5h | **Status**: Ready

**Description**:
Integration tests for event API endpoints using FastAPI TestClient and SQLite in-memory.

**Acceptance Criteria**:
- [ ] Test: GET /api/devices/1/events/system.pong — 200, returns parameters
- [ ] Test: GET /api/devices/1/events/system.pong — 404, event type not stored
- [ ] Test: GET /api/devices/9999/events/system.pong — 404, device not found
- [ ] Test: GET /api/devices/1/events/invalid.event — 400, unsupported event type
- [ ] Test: GET /api/devices/1/events — 200, returns dict of event_type → parameters
- [ ] Test: GET /api/devices/1/events — 200, returns `{}` when no events stored
- [ ] Test: GET /api/devices/9999/events — 404, device not found
- [ ] Tests in `tests/integration/test_event_api.py`
- [ ] Override `get_db` to use SQLite in-memory
- [ ] Override `init_db` to create tables (including DeviceEvent)

**Blocked by**: TASK-018
**Blocks**: None

---

## Task Summary

| Sprint | Tasks | Total Estimate |
|--------|-------|----------------|
| Sprint 4 | TASK-012 to TASK-014 | 3.5h |
| Sprint 5 | TASK-015 to TASK-016 | 3.5h |
| Sprint 6 | TASK-017 to TASK-018 | 1.5h |
| Sprint 7 | TASK-019 to TASK-020 | 3.5h |
| **Total** | **9 tasks** | **12h** |
