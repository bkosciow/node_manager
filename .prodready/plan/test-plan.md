# Test Plan

## Testing Strategy

### Test Pyramid

```
        /\
       /  \  Integration (30%)
      /----\
     /      \  Unit (70%)
    /--------\
   /          \
  /-----------\
```

No E2E browser tests for MVP — this is a backend-only service. Integration tests against the FastAPI TestClient cover the full HTTP surface.

## Unit Tests

**Coverage Target**: 80%+

| Module | What to Test |
|--------|--------------|
| `app/message_handler/device_discovery.py` | Message parsing, validation, cache logic, worker loop, IntegrityError handling |
| `app/crud/device.py` | CRUD operations, unique constraint enforcement, pagination |
| `app/models/device.py` | Model field types, unique constraint definition |

**Framework**: pytest
**Location**: `tests/unit/`

### Unit Test Cases

```markdown
### Message Handler (test_device_discovery.py)
- [ ] Valid message with chip_id + node → tuple pushed to queue
- [ ] None message → no exception, nothing queued
- [ ] Message with None data → no exception, nothing queued
- [ ] Missing chip_id in data → logged warning, skipped
- [ ] Missing node in data → logged warning, skipped
- [ ] Empty string chip_id → treated as missing, skipped
- [ ] Empty string node → treated as missing, skipped

### Discovery Worker / Cache
- [ ] Cache hit (pair in cache) → no DB query, no insert
- [ ] Cache miss + DB miss → device inserted, cache updated
- [ ] Cache miss + DB hit → no insert, cache warmed
- [ ] IntegrityError on insert → rollback, no crash, cache updated, warning logged
- [ ] Worker stops gracefully on stop_event
- [ ] Worker handles queue.Empty timeout (doesn't crash)

### CRUD (test_device_crud.py)
- [ ] create_device → returns device with auto-generated id and created_at
- [ ] get_device(existing_id) → returns device
- [ ] get_device(missing_id) → returns None
- [ ] get_device_by_pair(matching) → returns device
- [ ] get_device_by_pair(non_matching) → returns None
- [ ] get_devices → returns all devices
- [ ] get_devices(skip=1, limit=1) → returns correct page
- [ ] Duplicate insert → raises IntegrityError (unique constraint enforced)
```

## Integration Tests

**What to Test**:
- REST API endpoints (request → response)
- Full request lifecycle with SQLite in-memory DB

**Framework**: pytest + FastAPI TestClient
**Location**: `tests/integration/`

### API Test Cases

```markdown
### GET /api/devices (test_device_api.py)
- [ ] No devices → 200, empty array []
- [ ] Devices exist → 200, array of DeviceResponse objects
- [ ] Each device has id, chip_id, node, created_at
- [ ] Pagination: skip=1&limit=1 → at most 1 device, correct offset
- [ ] limit=1001 → 422 validation error
- [ ] limit=0 → 422 validation error (ge=1)
- [ ] skip=-1 → 422 validation error (ge=0)

### GET /api/devices/{device_id}
- [ ] Existing device → 200, device details
- [ ] Non-existent device → 404, "Device not found"
- [ ] device_id=0 → 422 validation error (ge=1)
```

### Test Database Setup

Integration tests override FastAPI dependencies:

```python
# tests/conftest.py
from fastapi.testclient import TestClient
from app.rest_server import app
from app.db.session import get_db, SessionLocal
from app.db.base import Base
from sqlalchemy import create_engine

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
```

## Test Data

### Fixtures

```python
# tests/conftest.py
SAMPLE_DEVICE_1 = {"chip_id": "ABC123", "node": "sensor-1"}
SAMPLE_DEVICE_2 = {"chip_id": "DEF456", "node": "sensor-2"}
SAMPLE_DEVICE_3 = {"chip_id": "ABC123", "node": "sensor-2"}  # same chip_id, different node
```

## CI Integration

Tests run on every PR/commit:
1. flake8 lint check
2. Unit tests (pytest tests/unit/)
3. Integration tests (pytest tests/integration/)

## Traceability

| User Story | Feature File | Test File |
|------------|--------------|-----------|
| US-001 | device-discovery.feature | tests/unit/test_device_discovery.py |
| US-002 | device-discovery.feature | tests/unit/test_device_discovery.py |
| US-003 | device-discovery.feature | tests/unit/test_device_discovery.py, tests/unit/test_device_crud.py |
| US-004 | device-api.feature | tests/integration/test_device_api.py |
| US-005 | device-api.feature | tests/integration/test_device_api.py |
| US-006 | device-discovery.feature | tests/unit/test_device_discovery.py |
