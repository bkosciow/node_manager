# Product Requirements Document (PRD) — Event Data Extension

## 1. Executive Summary

**Product**: IoT Device Discovery Service — Event Data Extension
**Problem**: IoT devices broadcast special events (`system.pong`, `system.microplate.hash`, `system.userspace.hash`) with runtime diagnostics and file hashes. These are currently ignored.
**Solution**: Detect these events in the existing message handler, upsert the latest JSON payload per device per event type, and expose via REST API.
**Target Users**: Single operator (solo developer), consumed by personal frontend.
**Success Metric**: Every supported event is stored; latest value is always retrievable.

## 2. Goals & Non-Goals

### Goals
- Capture `system.pong`, `system.microplate.hash`, `system.userspace.hash` events from incoming messages
- Store latest parameters as JSON, linked to the source Device
- Auto-create Device if unknown when event arrives
- Expose REST API to retrieve event data per device

### Non-Goals
- Historical tracking — only the latest value is kept
- Event payload validation — structure is unknown and unvalidated
- Real-time push — REST polling only
- Supporting event types beyond the 3 defined ones

## 3. Functional Requirements

### FR-1: Event Routing
- Inspect `message['event']` in incoming messages
- Route `system.pong`, `system.microplate.hash`, `system.userspace.hash` for storage
- All other events: proceed with normal device discovery only
- **Acceptance**: Supported events produce `DeviceEvent` records; unsupported events don't

### FR-2: Event Data Storage (Upsert)
- Store parameters as JSON in `DeviceEvent` table
- Unique constraint on `(device_id, event_type)` — one record per device per event type
- On arrival: insert if missing, update if exists (upsert)
- If device doesn't exist: create it first from `chip_id` + `node`
- **Acceptance**: Latest value always present; no duplicates; no orphaned events

### FR-3: Event Data API
- `GET /api/devices/{device_id}/events` — all event types for a device as `{event_type: parameters}`
- `GET /api/devices/{device_id}/events/{event_type}` — specific event type's parameters
- 404 if device missing or event type not found
- 400 if event type is unsupported
- Protected by existing `verify_token` pattern
- **Acceptance**: Frontend can fetch device state snapshot or individual event

## 4. Non-Functional Requirements

- **Performance**: Events processed in background worker (same thread as device discovery)
- **Reliability**: Graceful handling of DB errors — log and continue, never crash
- **Data**: Parameters stored as JSON — no schema validation
- **Deployment**: Same Docker container, same database

## 5. Data Model

### New Entity: DeviceEvent
- `id`: Integer PK
- `device_id`: Integer FK → devices.id (CASCADE delete)
- `event_type`: String(100) — one of 3 supported types
- `parameters`: JSON — raw event payload
- `updated_at`: DateTime — auto-set on upsert
- Unique constraint: `(device_id, event_type)`

### Relationship
- Device 1:N DeviceEvent (up to 3 per device — one per event type)

## 6. Architecture Integration

### Message Handler
- Existing `MessageHandler.handle()` extracts `chip_id` and `node` from `message.data`
- Add event detection after extraction: check `data.get('event')`, route to event queue
- Worker thread processes both device discovery tuples and event tuples

### CRUD
- New `app/crud/device_event.py`: `upsert_event(db, device_id, event_type, parameters)`
- Helper: `get_or_create_device(db, chip_id, node)` — returns existing or new Device

### REST API
- New endpoints in `app/rest_server.py` under `/api/devices/{device_id}/events`
- New Pydantic schemas in `app/schemas/device_event.py`

## 7. Scope & Timeline

- **MVP Features**: Event routing, upsert storage, auto-create device, 2 API endpoints
- **Future Features**: Historical timeline, hash change alerts, WebSocket push
- **Timeline**: No hard deadline
- **Team**: Solo developer

## 8. Open Questions & Risks

- JSON column type differs by dialect (JSONB on PostgreSQL, JSON on SQLite) — implementation must handle this
- Event volume per device is unknown — worker queue could grow if events arrive faster than DB writes
- The `message.data` dict is the source of truth for both device discovery and events — if message format changes, both features break

## 9. References

- User stories: `requirements/user-stories.md`
- Data model: `data-model/entities.md`, `data-model/models.py`
- Test scenarios: `test-scenarios/event-handling.feature`, `test-scenarios/event-api.feature`
- Existing codebase standards: `coding_standards.md`
