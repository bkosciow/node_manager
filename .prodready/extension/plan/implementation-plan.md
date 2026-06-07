# Implementation Plan — Event Data Extension

## Overview

Project: IoT Device Discovery Service — Event Data Extension
Pattern: Monolith extension (in-process, single tagged queue)
Stack: Python/FastAPI/SQLAlchemy 2.x/MySQL — inherited, zero new dependencies

## Phases

### Sprint 4: Event Data Layer
**Goal**: New model, schemas, and CRUD for DeviceEvent
- DeviceEvent SQLAlchemy model with JSON column and unique constraint
- Pydantic schemas for API responses
- CRUD: upsert_event, get_event, get_events, get_or_create_device

### Sprint 5: Event Handler Integration
**Goal**: Detect events in incoming messages and store them in background
- Extend MessageHandler.handle() — detect event_type, queue tagged items
- Extend worker loop — dispatch on tag, upsert DeviceEvent, auto-create Device

### Sprint 6: Event API
**Goal**: Expose event data via REST endpoints
- GET /api/devices/{device_id}/events/{event_type} — single event
- GET /api/devices/{device_id}/events — all events for a device

### Sprint 7: Tests
**Goal**: Unit + integration tests for the extension
- Unit: event routing, CRUD upsert, get_or_create_device
- Integration: API endpoints with TestClient

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| MySQL JSON column type differs from SQLite (dev tests) | Medium | Use SQLAlchemy `JSON` type — abstracts dialect. Integration tests use SQLite with JSON fallback. |
| Large event parameters slow queue throughput | Low | Current payloads ~200 bytes. Log warning if >1KB. |
| Worker dispatch adds complexity | Low | Tagged tuple pattern is simple. Single thread, no coordination. |

## Dependencies

- Existing `MessageHandler` in `app/message_handler/device_discovery.py` — extended in place
- Existing `Device` CRUD — reused for auto-create
- No external dependencies required
