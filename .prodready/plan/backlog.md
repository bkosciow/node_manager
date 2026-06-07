# Implementation Backlog

## Sprint 1: Data Layer & Discovery Engine

---

### TASK-001: Device SQLAlchemy Model
**Priority**: P0 | **Estimate**: 1h | **Status**: Ready

**Description**:
Create the `Device` SQLAlchemy model with `chip_id`, `node`, `created_at` fields and a composite unique constraint on `(chip_id, node)`.

**Acceptance Criteria**:
- [ ] `Device` model in `app/models/device.py` with `Mapped[]` + `mapped_column()` pattern
- [ ] Columns: `id` (PK, auto-increment), `chip_id` (String(255), not null), `node` (String(255), not null), `created_at` (DateTime, default=datetime.utcnow)
- [ ] Composite unique constraint: `UniqueConstraint("chip_id", "node", name="uq_chip_id_node")`
- [ ] Model registered in `app/models/__init__.py`
- [ ] Model import referenced in `app/db/base.py` or `app/db/session.py` so `create_all()` picks it up

**Blocked by**: None
**Blocks**: TASK-002, TASK-003

---

### TASK-002: Device Pydantic Schemas
**Priority**: P0 | **Estimate**: 0.5h | **Status**: Ready

**Description**:
Create Pydantic schemas for device creation and API response.

**Acceptance Criteria**:
- [ ] `DeviceCreate` schema in `app/schemas/device.py` with `chip_id: str` and `node: str`
- [ ] `DeviceResponse` schema with `id: int`, `chip_id: str`, `node: str`, `created_at: datetime`
- [ ] `DeviceCreate` validates non-empty strings for both fields
- [ ] Schema module created and importable

**Blocked by**: TASK-001
**Blocks**: TASK-003, TASK-007

---

### TASK-003: Device CRUD Operations
**Priority**: P0 | **Estimate**: 1.5h | **Status**: Ready

**Description**:
Implement CRUD functions for Device: get by id, get by (chip_id, node) pair, list with pagination, create with IntegrityError handling.

**Acceptance Criteria**:
- [ ] `get_device(db, device_id)` → `Optional[Device]`
- [ ] `get_device_by_pair(db, chip_id, node)` → `Optional[Device]`
- [ ] `get_devices(db, skip, limit)` → `list[Device]`
- [ ] `create_device(db, data: DeviceCreate)` → `Device` (commit + refresh)
- [ ] All functions in `app/crud/device.py`, re-exported from `app/crud/__init__.py`
- [ ] Follow coding standards: `model_dump(exclude_unset=True)` pattern for update (if applicable), proper session handling

**Blocked by**: TASK-001, TASK-002
**Blocks**: TASK-005

---

### TASK-004: Message Handler — Parse and Queue
**Priority**: P0 | **Estimate**: 1h | **Status**: Ready

**Description**:
Replace the stub `MessageHandler` with a full implementation that parses messages, extracts `(chip_id, node)`, validates, and pushes valid tuples onto a thread-safe queue.

**Acceptance Criteria**:
- [ ] `MessageHandler` in `app/message_handler/device_discovery.py` has a `queue.Queue` attribute
- [ ] `handle(message)` extracts `chip_id` and `node` from `message.data`
- [ ] If message is None or data is None: log and return (no exception)
- [ ] If `chip_id` or `node` missing from data: log warning and skip
- [ ] Valid messages push `(chip_id, node)` tuple to queue
- [ ] Handler never blocks on `queue.put()`

**Blocked by**: None
**Blocks**: TASK-005

---

### TASK-005: Discovery Worker — Cache, DB Upsert
**Priority**: P0 | **Estimate**: 2h | **Status**: Ready

**Description**:
Implement the background worker thread inside `MessageHandler` that drains the queue, checks the in-memory dedup cache, queries DB, and inserts new devices.

**Acceptance Criteria**:
- [ ] `MessageHandler` has `cache: set[tuple[str, str]]` attribute
- [ ] `MessageHandler` has `_stop_event: threading.Event` for graceful shutdown
- [ ] `start()` method launches daemon worker thread
- [ ] `stop()` method signals worker to halt
- [ ] Worker loop: `queue.get(timeout=0.5)` → process → loop (timeout allows stop check)
- [ ] `_process(chip_id, node)`: cache hit → skip. Cache miss → DB query. DB miss → insert. DB hit → add to cache.
- [ ] `IntegrityError` on insert: rollback, log warning, add to cache, continue (no crash)
- [ ] Each DB operation uses its own session (create from `SessionLocal`, close in finally)

**Blocked by**: TASK-003, TASK-004
**Blocks**: TASK-006

---

### TASK-006: Wire Handler into device_scaner.py
**Priority**: P0 | **Estimate**: 0.5h | **Status**: Ready

**Description**:
Update `device_scaner.py` to start the discovery worker on startup and stop it on shutdown.

**Acceptance Criteria**:
- [ ] After `MessageHandler()` is created, call `handler.start()` to launch worker thread
- [ ] On shutdown signal, call `handler.stop()` for graceful worker drain
- [ ] Worker thread is daemon (doesn't block process exit)
- [ ] No regression — existing scanner functionality preserved

**Blocked by**: TASK-005
**Blocks**: None

---

## Sprint 2: REST API

---

### TASK-007: Device List Endpoint
**Priority**: P0 | **Estimate**: 1h | **Status**: Ready

**Description**:
Create FastAPI REST server with `GET /api/devices` paginated endpoint. Follow existing coding standards (verify_token, response_model, tags).

**Acceptance Criteria**:
- [ ] FastAPI app in `app/rest_server.py` with `response_model`, `tags=["devices"]`
- [ ] `GET /api/devices` returns list of `DeviceResponse`
- [ ] Query params: `skip: int = Query(0, ge=0)`, `limit: int = Query(100, ge=1, le=1000)`
- [ ] Auth: `token: str = Depends(verify_token)` (graceful skip when API_TOKEN empty)
- [ ] DB dependency: `db: Session = Depends(get_db)`
- [ ] Returns empty array when no devices exist
- [ ] 422 when limit exceeds 1000 (Pydantic validation)
- [ ] `init_db()` called on FastAPI startup event
- [ ] Module has `logging.basicConfig` and `uvicorn.run()` entry point

**Blocked by**: TASK-002, TASK-003
**Blocks**: None

---

### TASK-008: Single Device Endpoint
**Priority**: P1 | **Estimate**: 0.5h | **Status**: Ready

**Description**:
Add `GET /api/devices/{device_id}` endpoint returning single device or 404.

**Acceptance Criteria**:
- [ ] `GET /api/devices/{device_id}` returns `DeviceResponse`
- [ ] 404 when device ID doesn't exist: `HTTPException(status_code=404, detail="Device not found")`
- [ ] Same auth pattern (`verify_token`)
- [ ] `device_id: int` path param with `ge=1`

**Blocked by**: TASK-007
**Blocks**: None

---

## Sprint 3: Tests

---

### TASK-009: Unit Tests — Handler & Cache
**Priority**: P1 | **Estimate**: 2h | **Status**: Ready

**Description**:
Unit tests for message handler parsing, validation, and cache logic.

**Acceptance Criteria**:
- [ ] Test: valid message → tuple pushed to queue
- [ ] Test: None message → no exception, nothing queued
- [ ] Test: None data → no exception, nothing queued
- [ ] Test: missing chip_id → logged and skipped
- [ ] Test: missing node → logged and skipped
- [ ] Test: cache hit → no DB query executed (mock DB)
- [ ] Test: cache miss → DB query executed (mock DB)
- [ ] Test: DB miss → insert called, cache updated
- [ ] Test: DB hit → no insert, cache warmed
- [ ] Test: IntegrityError on insert → rollback, no crash, cache updated
- [ ] Tests in `tests/unit/test_device_discovery.py`
- [ ] Use mocks for queue, DB session, CRUD functions

**Blocked by**: TASK-005
**Blocks**: None

---

### TASK-010: Unit Tests — CRUD
**Priority**: P1 | **Estimate**: 1h | **Status**: Ready

**Description**:
Unit tests for device CRUD operations using SQLite in-memory.

**Acceptance Criteria**:
- [ ] Test: create_device inserts and returns device with id
- [ ] Test: get_device returns device by id
- [ ] Test: get_device returns None for missing id
- [ ] Test: get_device_by_pair returns device for matching pair
- [ ] Test: get_device_by_pair returns None for non-matching pair
- [ ] Test: get_devices returns all devices
- [ ] Test: get_devices respects skip and limit
- [ ] Test: duplicate insert raises IntegrityError (unique constraint works)
- [ ] Tests in `tests/unit/test_device_crud.py`
- [ ] Use SQLite in-memory database (`sqlite:///:memory:`)

**Blocked by**: TASK-003
**Blocks**: None

---

### TASK-011: Integration Tests — API Endpoints
**Priority**: P1 | **Estimate**: 1.5h | **Status**: Ready

**Description**:
Integration tests for REST API endpoints using FastAPI TestClient and SQLite in-memory.

**Acceptance Criteria**:
- [ ] Test: GET /api/devices — 200, empty array when no devices
- [ ] Test: GET /api/devices — 200, returns devices with id, chip_id, node, created_at
- [ ] Test: GET /api/devices?skip=1&limit=1 — pagination works
- [ ] Test: GET /api/devices?limit=1001 — 422 validation error
- [ ] Test: GET /api/devices/1 — 200, returns device details
- [ ] Test: GET /api/devices/9999 — 404 not found
- [ ] Tests in `tests/integration/test_device_api.py`
- [ ] Override `get_db` to use SQLite in-memory
- [ ] Override `init_db` to create tables in test database
- [ ] Tests use `TestClient` from `fastapi.testclient`

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
