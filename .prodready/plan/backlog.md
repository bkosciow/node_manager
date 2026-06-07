# Implementation Backlog

## Sprint 1: Data Layer & Discovery Engine

---

### TASK-001: Device SQLAlchemy Model
**Priority**: P0 | **Estimate**: 1h | \*\*Status\*\*: Done

**Description**:
Create the `Device` SQLAlchemy model with `chip_id`, `node`, `created_at` fields and a composite unique constraint on `(chip_id, node)`.

**Acceptance Criteria**:
- [x] `Device` model in `app/models/device.py` with `Mapped[]` + `mapped_column()` pattern
- [x] Columns: `id` (PK, auto-increment), `chip_id` (String(255), not null), `node` (String(255), not null), `created_at` (DateTime, default=datetime.utcnow)
- [x] Composite unique constraint: `UniqueConstraint("chip_id", "node", name="uq_chip_id_node")`
- [x] Model registered in `app/models/__init__.py`
- [x] Model import referenced in `app/db/base.py` or `app/db/session.py` so `create_all()` picks it up

**Blocked by**: None
**Blocks**: TASK-002, TASK-003

---

### TASK-002: Device Pydantic Schemas
**Priority**: P0 | **Estimate**: 0.5h | \*\*Status\*\*: Done

**Description**:
Create Pydantic schemas for device creation and API response.

**Acceptance Criteria**:
- [x] `DeviceCreate` schema in `app/schemas/device.py` with `chip_id: str` and `node: str`
- [x] `DeviceResponse` schema with `id: int`, `chip_id: str`, `node: str`, `created_at: datetime`
- [x] `DeviceCreate` validates non-empty strings for both fields
- [x] Schema module created and importable

**Blocked by**: TASK-001
**Blocks**: TASK-003, TASK-007

---

### TASK-003: Device CRUD Operations
**Priority**: P0 | **Estimate**: 1.5h | \*\*Status\*\*: Done

**Description**:
Implement CRUD functions for Device: get by id, get by (chip_id, node) pair, list with pagination, create with IntegrityError handling.

**Acceptance Criteria**:
- [x] `get_device(db, device_id)` → `Optional[Device]`
- [x] `get_device_by_pair(db, chip_id, node)` → `Optional[Device]`
- [x] `get_devices(db, skip, limit)` → `list[Device]`
- [x] `create_device(db, data: DeviceCreate)` → `Device` (commit + refresh)
- [x] All functions in `app/crud/device.py`, re-exported from `app/crud/__init__.py`
- [x] Follow coding standards: `model_dump(exclude_unset=True)` pattern for update (if applicable), proper session handling

**Blocked by**: TASK-001, TASK-002
**Blocks**: TASK-005

---

### TASK-004: Message Handler — Parse and Queue
**Priority**: P0 | **Estimate**: 1h | \*\*Status\*\*: Done

**Description**:
Replace the stub `MessageHandler` with a full implementation that parses messages, extracts `(chip_id, node)`, validates, and pushes valid tuples onto a thread-safe queue.

**Acceptance Criteria**:
- [x] `MessageHandler` in `app/message_handler/device_discovery.py` has a `queue.Queue` attribute
- [x] `handle(message)` extracts `chip_id` and `node` from `message.data`
- [x] If message is None or data is None: log and return (no exception)
- [x] If `chip_id` or `node` missing from data: log warning and skip
- [x] Valid messages push `(chip_id, node)` tuple to queue
- [x] Handler never blocks on `queue.put()`

**Blocked by**: None
**Blocks**: TASK-005

---

### TASK-005: Discovery Worker — Cache, DB Upsert
**Priority**: P0 | **Estimate**: 2h | \*\*Status\*\*: Done

**Description**:
Implement the background worker thread inside `MessageHandler` that drains the queue, checks the in-memory dedup cache, queries DB, and inserts new devices.

**Acceptance Criteria**:
- [x] `MessageHandler` has `cache: set[tuple[str, str]]` attribute
- [x] `MessageHandler` has `_stop_event: threading.Event` for graceful shutdown
- [x] `start()` method launches daemon worker thread
- [x] `stop()` method signals worker to halt
- [x] Worker loop: `queue.get(timeout=0.5)` → process → loop (timeout allows stop check)
- [x] `_process(chip_id, node)`: cache hit → skip. Cache miss → DB query. DB miss → insert. DB hit → add to cache.
- [x] `IntegrityError` on insert: rollback, log warning, add to cache, continue (no crash)
- [x] Each DB operation uses its own session (create from `SessionLocal`, close in finally)

**Blocked by**: TASK-003, TASK-004
**Blocks**: TASK-006

---

### TASK-006: Wire Handler into device_scaner.py
**Priority**: P0 | **Estimate**: 0.5h | \*\*Status\*\*: Done

**Description**:
Update `device_scaner.py` to start the discovery worker on startup and stop it on shutdown.

**Acceptance Criteria**:
- [x] After `MessageHandler()` is created, call `handler.start()` to launch worker thread
- [x] On shutdown signal, call `handler.stop()` for graceful worker drain
- [x] Worker thread is daemon (doesn't block process exit)
- [x] No regression — existing scanner functionality preserved

**Blocked by**: TASK-005
**Blocks**: None

---

## Sprint 2: REST API

---

### TASK-007: Device List Endpoint
**Priority**: P0 | **Estimate**: 1h | \*\*Status\*\*: Done

**Description**:
Create FastAPI REST server with `GET /api/devices` paginated endpoint. Follow existing coding standards (verify_token, response_model, tags).

**Acceptance Criteria**:
- [x] FastAPI app in `app/rest_server.py` with `response_model`, `tags=["devices"]`
- [x] `GET /api/devices` returns list of `DeviceResponse`
- [x] Query params: `skip: int = Query(0, ge=0)`, `limit: int = Query(100, ge=1, le=1000)`
- [x] Auth: `token: str = Depends(verify_token)` (graceful skip when API_TOKEN empty)
- [x] DB dependency: `db: Session = Depends(get_db)`
- [x] Returns empty array when no devices exist
- [x] 422 when limit exceeds 1000 (Pydantic validation)
- [x] `init_db()` called on FastAPI startup event
- [x] Module has `logging.basicConfig` and `uvicorn.run()` entry point

**Blocked by**: TASK-002, TASK-003
**Blocks**: None

---

### TASK-008: Single Device Endpoint
**Priority**: P1 | **Estimate**: 0.5h | \*\*Status\*\*: Done

**Description**:
Add `GET /api/devices/{device_id}` endpoint returning single device or 404.

**Acceptance Criteria**:
- [x] `GET /api/devices/{device_id}` returns `DeviceResponse`
- [x] 404 when device ID doesn't exist: `HTTPException(status_code=404, detail="Device not found")`
- [x] Same auth pattern (`verify_token`)
- [x] `device_id: int` path param with `ge=1`

**Blocked by**: TASK-007
**Blocks**: None

---

## Sprint 3: Tests

---

### TASK-009: Unit Tests — Handler & Cache
**Priority**: P1 | **Estimate**: 2h | \*\*Status\*\*: Done

**Description**:
Unit tests for message handler parsing, validation, and cache logic.

**Acceptance Criteria**:
- [x] Test: valid message → tuple pushed to queue
- [x] Test: None message → no exception, nothing queued
- [x] Test: None data → no exception, nothing queued
- [x] Test: missing chip_id → logged and skipped
- [x] Test: missing node → logged and skipped
- [x] Test: cache hit → no DB query executed (mock DB)
- [x] Test: cache miss → DB query executed (mock DB)
- [x] Test: DB miss → insert called, cache updated
- [x] Test: DB hit → no insert, cache warmed
- [x] Test: IntegrityError on insert → rollback, no crash, cache updated
- [x] Tests in `tests/unit/test_device_discovery.py`
- [x] Use mocks for queue, DB session, CRUD functions

**Blocked by**: TASK-005
**Blocks**: None

---

### TASK-010: Unit Tests — CRUD
**Priority**: P1 | **Estimate**: 1h | \*\*Status\*\*: Done

**Description**:
Unit tests for device CRUD operations using SQLite in-memory.

**Acceptance Criteria**:
- [x] Test: create_device inserts and returns device with id
- [x] Test: get_device returns device by id
- [x] Test: get_device returns None for missing id
- [x] Test: get_device_by_pair returns device for matching pair
- [x] Test: get_device_by_pair returns None for non-matching pair
- [x] Test: get_devices returns all devices
- [x] Test: get_devices respects skip and limit
- [x] Test: duplicate insert raises IntegrityError (unique constraint works)
- [x] Tests in `tests/unit/test_device_crud.py`
- [x] Use SQLite in-memory database (`sqlite:///:memory:`)

**Blocked by**: TASK-003
**Blocks**: None

---

### TASK-011: Integration Tests — API Endpoints
**Priority**: P1 | **Estimate**: 1.5h | \*\*Status\*\*: Done

**Description**:
Integration tests for REST API endpoints using FastAPI TestClient and SQLite in-memory.

**Acceptance Criteria**:
- [x] Test: GET /api/devices — 200, empty array when no devices
- [x] Test: GET /api/devices — 200, returns devices with id, chip_id, node, created_at
- [x] Test: GET /api/devices?skip=1&limit=1 — pagination works
- [x] Test: GET /api/devices?limit=1001 — 422 validation error
- [x] Test: GET /api/devices/1 — 200, returns device details
- [x] Test: GET /api/devices/9999 — 404 not found
- [x] Tests in `tests/integration/test_device_api.py`
- [x] Override `get_db` to use SQLite in-memory
- [x] Override `init_db` to create tables in test database
- [x] Tests use `TestClient` from `fastapi.testclient`

**Blocked by**: TASK-008
**Blocks**: None

---

## Task Summary

| Sprint | Tasks | Total Estimate |
|--------|-------|----------------|
| Sprint 1 | TASK-001 to TASK-006 | 6h |
| Sprint 2 | TASK-007 to TASK-008 | 1.5h |
| Sprint 3 | TASK-009 to TASK-011 | 4.5h |
| **Total** | **11 tasks** | **12h** |
