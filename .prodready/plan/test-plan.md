# Test Plan

## Testing Strategy

### Test Pyramid

```
       /  \
      /    \  Integration (30%)
     /------\
    /        \  Unit (70%)
   /----------\
```

No E2E browser tests for MVP — this is a backend-only service. Integration tests against the FastAPI TestClient cover the full HTTP surface.

## Unit Tests

**Coverage Target**: 80%+

| Module | What to Test |
|--------|--------------|
| `app/message_handler/device_discovery.py` | Message parsing, validation, cache logic, worker loop, IntegrityError handling |
| `app/crud/device.py` | CRUD operations, unique constraint enforcement, pagination |
| `app/crud/device_event.py` | Upsert logic, get by pair, list by device |
| `app/models/device.py` | Model field types, unique constraint definition |
| `app/models/device_event.py` | Model field types, composite unique constraint |
| `app/schemas/device_event.py` | Pydantic validation (required fields, event_type non-empty, parameters optional) |
| `repo_scanner.py` | Directory walking, SHA256 computation, file sync logic, error handling |

**Framework**: pytest
**Location**: `tests/unit/`

### Unit Test Cases

```markdown
### Message Handler (test_device_discovery.py)
- [x] Valid message with chip_id + node → tuple pushed to queue
- [x] None message → no exception, nothing queued
- [x] Message with None data → no exception, nothing queued
- [x] Missing chip_id in data → logged warning, skipped
- [x] Missing node in data → logged warning, skipped
- [x] Empty string chip_id → treated as missing, skipped
- [x] Empty string node → treated as missing, skipped

### Discovery Worker / Cache
- [x] Cache hit (pair in cache) → no DB query, no insert
- [x] Cache miss + DB miss → device inserted, cache updated
- [x] Cache miss + DB hit → no insert, cache warmed
- [x] IntegrityError on insert → rollback, no crash, cache updated, warning logged
- [x] Worker stops gracefully on stop_event
- [x] Worker handles queue.Empty timeout (doesn't crash)

### CRUD (test_device_crud.py)
- [x] create_device → returns device with auto-generated id and created_at
- [x] get_device(existing_id) → returns device
- [x] get_device(missing_id) → returns None
- [x] get_device_by_pair(matching) → returns device
- [x] get_device_by_pair(non_matching) → returns None
- [x] get_devices → returns all devices
- [x] get_devices(skip=1, limit=1) → returns correct page
- [x] Duplicate insert → raises IntegrityError (unique constraint enforced)

### DeviceEvent Model (test_device_event_model.py)
- [x] Model has correct columns (id, device_id, event_type, parameters, logged_at)
- [x] Composite unique constraint on (device_id, event_type)
- [x] Relationship to Device works

### DeviceEvent Schemas (test_device_event_schemas.py)
- [x] DeviceEventCreate validates required fields (device_id, event_type)
- [x] DeviceEventCreate accepts parameters as dict or None
- [x] DeviceEventUpdate has all fields as Optional
- [x] event_type validator rejects empty strings

### DeviceEvent CRUD (test_event_crud.py)
- [x] upsert_event inserts new event
- [x] upsert_event updates existing event (same device_id + event_type)
- [x] get_event returns event for matching pair
- [x] get_event returns None for missing pair
- [x] get_events returns all events for a device

### Repository Scanner (test_repo_scanner.py)
- [ ] Scanner walks /upgrades and identifies repos by folder structure
- [ ] Scanner computes correct SHA256 for a file
- [ ] Scanner creates Repository record for new repo
- [ ] Scanner upserts RepositoryFile records (new + updated)
- [ ] Scanner removes RepositoryFile records for deleted files
- [ ] Scanner handles unreadable file (logs error, continues)
- [ ] Scanner handles missing /upgrades directory gracefully
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
- [x] No devices → 200, empty array []
- [x] Devices exist → 200, array of DeviceResponse objects
- [x] Each device has id, chip_id, node, created_at
- [x] Pagination: skip=1&limit=1 → at most 1 device, correct offset
- [x] limit=1001 → 422 validation error
- [x] limit=0 → 422 validation error (ge=1)
- [x] skip=-1 → 422 validation error (ge=0)

### GET /api/devices/{device_id}
- [x] Existing device → 200, device details
- [x] Non-existent device → 404, "Device not found"
- [x] device_id=0 → 422 validation error (ge=1)

### GET /api/devices/{device_id}/events/{event_type} (test_event_api.py)
- [x] Existing event → 200, event with parameters
- [x] Non-existent event → 404
- [x] Non-existent device → 404

### GET /api/devices/{device_id}/events
- [x] Device with events → 200, list of events
- [x] Device with no events → 200, empty list

### GET /api/repos?type={type} (test_repo_api.py)
- [ ] No repos of type → 200, empty list []
- [ ] Repos exist → 200, list with name, type, files (filename + sha256)
- [ ] Invalid type → 400 bad request
- [ ] type=microplate → returns only microplate repos
- [ ] type=userspace → returns only userspace repos

### POST /api/nodes/{device_id}/repos
- [ ] Valid assignment → 200, assignment created
- [ ] Replace existing assignment of same type → old removed, new created
- [ ] Non-existent device → 404
- [ ] Non-existent repository → 404
- [ ] Assign second type to same node → both assignments exist
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

SAMPLE_REPO = {"name": "node_north", "repo_type": "microplate"}
SAMPLE_FILE = {"filename": "core.py", "sha256": "a" * 64}
```

### Temp Directory for Scanner Tests

```python
# tests/unit/test_repo_scanner.py
import tempfile
import os

@pytest.fixture
def upgrades_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(f"{tmpdir}/node_north/_microplate")
        with open(f"{tmpdir}/node_north/_microplate/core.py", "w") as f:
            f.write("print('hello')")
        yield tmpdir
```

## CI Integration

Tests run on every PR/commit:
1. flake8 lint check
2. Unit tests (pytest tests/unit/)
3. Integration tests (pytest tests/integration/)

## Traceability

| User Story | Feature File | Test File(s) |
|------------|--------------|--------------|
| US-001 | device-discovery.feature | tests/unit/test_device_discovery.py |
| US-002 | device-discovery.feature | tests/unit/test_device_discovery.py |
| US-003 | device-discovery.feature | tests/unit/test_device_discovery.py, tests/unit/test_device_crud.py |
| US-004 | device-api.feature | tests/integration/test_device_api.py |
| US-005 | device-api.feature | tests/integration/test_device_api.py |
| US-006 | device-discovery.feature | tests/unit/test_device_discovery.py |
| US-007 | repository-management.feature | tests/unit/test_repo_scanner.py |
| US-008 | repository-management.feature | tests/integration/test_repo_api.py |
| US-009 | repository-management.feature | tests/integration/test_repo_api.py |
