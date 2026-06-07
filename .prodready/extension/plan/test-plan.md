# Test Plan — Event Data Extension

## Testing Strategy

### Test Pyramid

```
        /\
       /  \  E2E (covered by existing Sprint 3 integration tests)
      /----\
     /      \  Integration (~25%) — API endpoint tests
    /--------\
   /          \  Unit (~75%) — handler routing, CRUD, schemas
  /-----------\
```

## Unit Tests

**Framework**: pytest (existing)
**Location**: `tests/unit/`

### Handler & Worker (`test_event_handler.py`)

| Test | What to Verify |
|------|----------------|
| system.pong event | Event tuple queued with `"event"` tag |
| system.microplate.hash event | Event tuple queued |
| system.userspace.hash event | Event tuple queued |
| Unrecognized event | Only `"device"` tuple queued |
| No event field | Only `"device"` tuple queued |
| Missing parameters | Defaults to `{}` |
| Worker dispatch device tag | `_process` called (mock) |
| Worker dispatch event tag | `_process_event` called (mock) |
| `_process_event` IntegrityError | Logged, no crash |

### CRUD (`test_event_crud.py`)

| Test | What to Verify |
|------|----------------|
| upsert — insert | New record created with correct fields |
| upsert — update | Existing record parameters + updated_at changed |
| get_event — found | Returns DeviceEvent for matching device_id + event_type |
| get_event — not found | Returns None |
| get_events — multiple | Returns all events for device |
| get_events — none | Returns empty list |
| get_or_create — exists | Returns existing Device |
| get_or_create — new | Creates and returns new Device |
| get_or_create — IntegrityError | Returns existing (concurrent insert) |

**Database**: SQLite in-memory for CRUD tests

## Integration Tests

**Framework**: pytest + FastAPI TestClient (existing)
**Location**: `tests/integration/`

### Event API (`test_event_api.py`)

| Test | Expected |
|------|----------|
| GET /api/devices/1/events/system.pong — exists | 200, parameters dict |
| GET /api/devices/1/events/system.pong — missing | 404 |
| GET /api/devices/9999/events/system.pong | 404 |
| GET /api/devices/1/events/invalid.event | 400 |
| GET /api/devices/1/events — has events | 200, `{event_type: params}` |
| GET /api/devices/1/events — no events | 200, `{}` |
| GET /api/devices/9999/events | 404 |

**Database**: SQLite in-memory, override `get_db` + `init_db`

## Traceability

| User Story | Feature File | Unit Test | Integration Test |
|------------|--------------|-----------|------------------|
| US-007 | event-handling.feature | test_event_handler.py | — |
| US-008 | event-handling.feature | test_event_crud.py | — |
| US-009 | event-handling.feature | test_event_crud.py | — |
| US-010 | event-api.feature | — | test_event_api.py |
| US-011 | event-api.feature | — | test_event_api.py |
| US-012 | event-handling.feature | test_event_handler.py | — |

## CI Integration

Tests run via existing CI pipeline:
1. `flake8 .` — lint check
2. `pytest tests/unit/` — unit tests
3. `pytest tests/integration/` — integration tests (SQLite in-memory)
