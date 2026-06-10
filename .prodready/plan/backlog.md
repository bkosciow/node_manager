# Implementation Backlog

## Sprint 1: Device Data Layer & Discovery Engine

---

### TASK-001: Device SQLAlchemy Model
**Priority**: P0 | **Estimate**: 1h | **Status**: Done

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
**Priority**: P0 | **Estimate**: 0.5h | **Status**: Done

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
**Priority**: P0 | **Estimate**: 1.5h | **Status**: Done

**Description**:
Implement CRUD functions for Device: get by id, get by (chip_id, node) pair, list with pagination, create with IntegrityError handling.

**Acceptance Criteria**:
- [x] `get_device(db, device_id)` → `Optional[Device]`
- [x] `get_device_by_pair(db, chip_id, node)` → `Optional[Device]`
- [x] `get_devices(db, skip, limit)` → `list[Device]`
- [x] `create_device(db, data: DeviceCreate)` → `Device` (commit + refresh)
- [x] All functions in `app/crud/device.py`, re-exported from `app/crud/__init__.py`
- [x] Follow coding standards: `model_dump(exclude_unset=True)` pattern for update, proper session handling

**Blocked by**: TASK-001, TASK-002
**Blocks**: TASK-005

---

### TASK-004: Message Handler — Parse and Queue
**Priority**: P0 | **Estimate**: 1h | **Status**: Done

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
**Priority**: P0 | **Estimate**: 2h | **Status**: Done

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
**Priority**: P0 | **Estimate**: 0.5h | **Status**: Done

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

## Sprint 2: Device REST API

---

### TASK-007: Device List Endpoint
**Priority**: P0 | **Estimate**: 1h | **Status**: Done

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
**Priority**: P1 | **Estimate**: 0.5h | **Status**: Done

**Description**:
Add `GET /api/devices/{device_id}` endpoint returning single device or 404.

**Acceptance Criteria**:
- [x] `GET /api/devices/{device_id}` returns `DeviceResponse`
- [x] 404 when device ID doesn't exist: `HTTPException(status_code=404, detail="Device not found")`
- [x] Same auth pattern (`verify_token`)
- [x] `device_id: int` path param with `ge=1`

**Blocked by**: TASK-007
**Blocks**: TASK-012

---

## Sprint 3: Device Events

---

### TASK-009: DeviceEvent SQLAlchemy Model
**Priority**: P0 | **Estimate**: 1h | **Status**: Done

**Description**:
Create the `DeviceEvent` SQLAlchemy model with `device_id` (FK), `event_type`, `parameters` (JSON), `logged_at` fields and a composite unique constraint on `(device_id, event_type)`.

**Acceptance Criteria**:
- [x] `DeviceEvent` model in `app/models/device_event.py` with `Mapped[]` + `mapped_column()` pattern
- [x] Columns: `id` (PK), `device_id` (FK → devices.id, CASCADE), `event_type` (String(100), not null), `parameters` (JSON/Text, nullable), `logged_at` (DateTime, default=datetime.utcnow)
- [x] Composite unique constraint: `UniqueConstraint("device_id", "event_type", name="uq_device_event_type")`
- [x] Relationship to `Device` via `back_populates`
- [x] Model registered in `app/models/__init__.py`

**Blocked by**: TASK-001
**Blocks**: TASK-010, TASK-011

---

### TASK-010: DeviceEvent Pydantic Schemas
**Priority**: P0 | **Estimate**: 0.5h | **Status**: Done

**Description**:
Create Pydantic schemas for device event creation and API response.

**Acceptance Criteria**:
- [x] `DeviceEventCreate` schema with `device_id: int`, `event_type: str`, `parameters: dict | None`
- [x] `DeviceEventResponse` schema with `id`, `device_id`, `event_type`, `parameters`, `logged_at`
- [x] `DeviceEventUpdate` schema with all fields as `Optional[type] = None`
- [x] Validators on `event_type` (non-empty string)
- [x] Schemas in `app/schemas/device_event.py`

**Blocked by**: TASK-009
**Blocks**: TASK-011, TASK-012

---

### TASK-011: DeviceEvent CRUD (Upsert Pattern)
**Priority**: P0 | **Estimate**: 1.5h | **Status**: Done

**Description**:
Implement CRUD for DeviceEvent using upsert pattern: insert if new (device_id + event_type), update if exists.

**Acceptance Criteria**:
- [x] `upsert_event(db, data: DeviceEventCreate)` → `DeviceEvent` (insert or update existing)
- [x] `get_event(db, device_id, event_type)` → `Optional[DeviceEvent]`
- [x] `get_events(db, device_id)` → `list[DeviceEvent]`
- [x] Upsert uses `INSERT ... ON DUPLICATE KEY UPDATE` (MySQL) or equivalent
- [x] Functions in `app/crud/device_event.py`, re-exported from `app/crud/__init__.py`

**Blocked by**: TASK-009, TASK-010
**Blocks**: TASK-012

---

### TASK-012: Event API Endpoints
**Priority**: P1 | **Estimate**: 1h | **Status**: Done

**Description**:
Add endpoints for logged events: get single event by device+type, list all events for a device.

**Acceptance Criteria**:
- [x] `GET /api/devices/{device_id}/events/{event_type}` returns `DeviceEventResponse`
- [x] `GET /api/devices/{device_id}/events` returns list of events for the device
- [x] 404 when device doesn't exist
- [x] 404 when specific event doesn't exist
- [x] Same auth pattern (`verify_token`)
- [x] `tags=["device-events"]`

**Blocked by**: TASK-008, TASK-011
**Blocks**: TASK-025

---

## Sprint 4: Repository Data Layer & Scanner

---

### TASK-013: Repository + RepositoryFile SQLAlchemy Models
**Priority**: P0 | **Estimate**: 1.5h | **Status**: Done

**Description**:
Create `Repository` and `RepositoryFile` SQLAlchemy models with relationships and unique constraints.

**Acceptance Criteria**:
- [ ] `Repository` model: `id` (PK), `name` (String(255)), `repo_type` (String(50)), `created_at` (DateTime)
- [ ] `Repository` unique constraint: `UniqueConstraint("name", "repo_type", name="uq_repo_name_type")`
- [ ] `RepositoryFile` model: `id` (PK), `repository_id` (FK → repositories.id, CASCADE), `filename` (String(255)), `sha256` (String(64)), `updated_at` (DateTime)
- [ ] `RepositoryFile` unique constraint: `UniqueConstraint("repository_id", "filename", name="uq_repo_file")`
- [ ] Relationship: `Repository.files` → `list[RepositoryFile]` with `cascade="all, delete-orphan"`
- [ ] Models in `app/models/repository.py`, registered in `__init__.py`

**Blocked by**: None
**Blocks**: TASK-014, TASK-015

---

### TASK-014: Repository Pydantic Schemas
**Priority**: P0 | **Estimate**: 0.5h | **Status**: Done

**Description**:
Create Pydantic schemas for repository creation, file records, and nested API responses.

**Acceptance Criteria**:
- [ ] `RepositoryCreate` schema: `name: str`, `repo_type: str`
- [ ] `RepositoryFileResponse` schema: `id`, `filename`, `sha256`, `updated_at`
- [ ] `RepositoryResponse` schema: `id`, `name`, `repo_type`, `files: list[RepositoryFileResponse]`, `created_at`
- [ ] `repo_type` validator: must be one of `["microplate", "userspace"]`
- [ ] Schemas in `app/schemas/repository.py`

**Blocked by**: TASK-013
**Blocks**: TASK-015, TASK-019

---

### TASK-015: Repository CRUD
**Priority**: P0 | **Estimate**: 2h | **Status**: Done

**Description**:
Implement CRUD for Repository and RepositoryFile: create repo, list by type, file upsert, file cleanup.

**Acceptance Criteria**:
- [ ] `get_repository(db, repo_id)` → `Optional[Repository]`
- [ ] `get_repositories(db, repo_type: str)` → `list[Repository]` (with eager-loaded files)
- [ ] `create_repository(db, data: RepositoryCreate)` → `Repository`
- [ ] `upsert_repository_file(db, repo_id, filename, sha256)` → `RepositoryFile`
- [ ] `cleanup_repository_files(db, repo_id, existing_filenames: set[str])` → `int` (deleted count)
- [ ] Functions in `app/crud/repository.py`, re-exported from `app/crud/__init__.py`

**Blocked by**: TASK-013, TASK-014
**Blocks**: TASK-016, TASK-019

---

### TASK-016: Repository Scanner Script
**Priority**: P0 | **Estimate**: 2h | **Status**: Done

**Description**:
Create standalone Python script that walks `/upgrades`, computes SHA256 for every file, and syncs to DB. Runs as a separate Docker container (not FastAPI).

**Acceptance Criteria**:
- [ ] Script at `repo_scanner.py` (standalone, `if __name__ == "__main__"` entrypoint)
- [ ] Walks `/upgrades/` directory, identifies repos by folder structure: `{repo_name}/{_microplate|_userspace}/`
- [ ] Computes SHA256 for every file in each repo subfolder
- [ ] For each repo: creates/updates `Repository` record, upserts `RepositoryFile` records
- [ ] Removes `RepositoryFile` records for files no longer on disk
- [ ] Uses same `DATABASE_URL` from config (`app.config.settings`)
- [ ] Logs errors per file and continues (no crash on unreadable file)
- [ ] No FastAPI dependency — creates DB session manually with try/finally

**Blocked by**: TASK-015
**Blocks**: TASK-024

---

## Sprint 5: Repository REST API & Assignments

---

### TASK-017: NodeRepository Model + Schemas
**Priority**: P0 | **Estimate**: 1h | **Status**: Done

**Description**:
Create `NodeRepository` model for repo-to-node assignments and associated Pydantic schemas.

**Acceptance Criteria**:
- [ ] `NodeRepository` model: `id` (PK), `device_id` (FK → devices.id, CASCADE), `repository_id` (FK → repositories.id, CASCADE), `repo_type` (String(50)), `assigned_at` (DateTime)
- [ ] Unique constraint: `UniqueConstraint("device_id", "repo_type", name="uq_device_repo_type")`
- [ ] Relationships: `device` (back_populates), `repository` (back_populates)
- [ ] `RepoAssignmentCreate` schema: `repository_id: int`
- [ ] `RepoAssignmentResponse` schema: `id`, `device_id`, `repository_id`, `repo_type`, `assigned_at`
- [ ] Model in `app/models/node_repository.py`, schemas in `app/schemas/node_repository.py`

**Blocked by**: TASK-001, TASK-013
**Blocks**: TASK-018

---

### TASK-018: NodeRepository CRUD (Assign with Replace)
**Priority**: P0 | **Estimate**: 1.5h | **Status**: Done

**Description**:
Implement CRUD for NodeRepository. Key behavior: assigning a repo of the same type to a node replaces the old assignment.

**Acceptance Criteria**:
- [x] `assign_repo_to_node(db, device_id, repository_id, repo_type)` → `NodeRepository`
- [x] If assignment of same type exists for device: delete old, insert new
- [x] Validate device exists (return None if not)
- [x] Validate repository exists (return None if not)
- [x] `get_assignments(db, device_id)` → `list[NodeRepository]`
- [x] Functions in `app/crud/node_repository.py`, re-exported from `app/crud/__init__.py`

**Blocked by**: TASK-017
**Blocks**: TASK-020

---

### TASK-019: Repo List Endpoint
**Priority**: P0 | **Estimate**: 1h | **Status**: Done

**Description**:
Add `GET /api/repos?type={microplate|userspace}` endpoint returning repos with their files and hashes.

**Acceptance Criteria**:
- [x] `GET /api/repos?type=microplate` returns list of repos with nested files
- [x] `type` query param is required, validated against `["microplate", "userspace"]`
- [x] 400 when invalid type is provided
- [x] Returns empty list when no repos match the type
- [x] Response includes repo name, type, files (filename + sha256 + updated_at)
- [x] `tags=["repos"]`
- [x] Same auth pattern (`verify_token`)

**Blocked by**: TASK-015, TASK-014
**Blocks**: None

---

### TASK-020: Repo Assignment Endpoint
**Priority**: P0 | **Estimate**: 1h | **Status**: Done

**Description**:
Add `POST /api/nodes/{device_id}/repos` endpoint for assigning repos to nodes.

**Acceptance Criteria**:
- [x] `POST /api/nodes/{device_id}/repos` with body `{repository_id: int}`
- [x] Returns `RepoAssignmentResponse` on success
- [x] 404 when device doesn't exist
- [x] 404 when repository doesn't exist
- [x] Replaces existing assignment of the same type
- [x] `tags=["assignments"]`
- [x] Same auth pattern (`verify_token`)

**Blocked by**: TASK-018
**Blocks**: None

---

## Sprint 6: Tests

---

### TASK-021: Unit Tests — Message Handler & Cache
**Priority**: P1 | **Estimate**: 2h | **Status**: Done

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

### TASK-022: Unit Tests — Device CRUD
**Priority**: P1 | **Estimate**: 1h | **Status**: Done

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
- [x] Use SQLite in-memory database

**Blocked by**: TASK-003
**Blocks**: None

---

### TASK-023: Unit Tests — Event Model, Schemas, CRUD
**Priority**: P1 | **Estimate**: 1.5h | **Status**: Done

**Description**:
Unit tests for DeviceEvent model, Pydantic schemas, and CRUD upsert logic.

**Acceptance Criteria**:
- [x] Test: DeviceEvent model has correct columns and unique constraint
- [x] Test: DeviceEventCreate validates required fields
- [x] Test: DeviceEventCreate validates event_type non-empty
- [x] Test: DeviceEventUpdate has all fields as Optional
- [x] Test: upsert_event inserts new event
- [x] Test: upsert_event updates existing event (same device_id + event_type)
- [x] Test: get_event returns event for matching pair
- [x] Test: get_events returns all events for a device
- [x] Tests in `tests/unit/test_device_event_model.py`, `test_device_event_schemas.py`, `test_event_crud.py`

**Blocked by**: TASK-011
**Blocks**: None

---

### TASK-024: Unit Tests — Repository Scanner
**Priority**: P1 | **Estimate**: 1.5h | **Status**: Ready

**Description**:
Unit tests for repository scanner logic: directory walking, SHA256 computation, file sync.

**Acceptance Criteria**:
- [ ] Test: scanner walks /upgrades and identifies repos by folder structure
- [ ] Test: scanner computes correct SHA256 for a file
- [ ] Test: scanner creates Repository record for new repo
- [ ] Test: scanner upserts RepositoryFile records (new + updated)
- [ ] Test: scanner removes RepositoryFile records for deleted files
- [ ] Test: scanner handles unreadable file (logs error, continues)
- [ ] Test: scanner handles missing /upgrades directory gracefully
- [ ] Tests in `tests/unit/test_repo_scanner.py`
- [ ] Use temp directory with mock file structure

**Blocked by**: TASK-016
**Blocks**: None

---

### TASK-025: Integration Tests — Device + Event API
**Priority**: P1 | **Estimate**: 1.5h | **Status**: Done

**Description**:
Integration tests for device and event REST API endpoints using FastAPI TestClient and SQLite in-memory.

**Acceptance Criteria**:
- [x] Test: GET /api/devices — 200, empty array when no devices
- [x] Test: GET /api/devices — 200, returns devices with id, chip_id, node, created_at
- [x] Test: GET /api/devices?skip=1&limit=1 — pagination works
- [x] Test: GET /api/devices?limit=1001 — 422 validation error
- [x] Test: GET /api/devices/1 — 200, returns device details
- [x] Test: GET /api/devices/9999 — 404 not found
- [x] Test: GET /api/devices/1/events/firmware_update — 200, returns event
- [x] Test: GET /api/devices/1/events — 200, returns all events for device
- [x] Test: GET /api/devices/1/events/missing — 404 event not found
- [x] Tests in `tests/integration/test_device_api.py`, `test_event_api.py`
- [x] Override `get_db` to use SQLite in-memory

**Blocked by**: TASK-012
**Blocks**: None

---

### TASK-026: Integration Tests — Repo + Assignment API
**Priority**: P1 | **Estimate**: 2h | **Status**: Ready

**Description**:
Integration tests for repository and assignment REST API endpoints.

**Acceptance Criteria**:
- [ ] Test: GET /api/repos?type=microplate — 200, empty list when no repos
- [ ] Test: GET /api/repos?type=microplate — 200, returns repos with files
- [ ] Test: GET /api/repos?type=invalid — 400 bad request
- [ ] Test: POST /api/nodes/1/repos — 200, creates assignment
- [ ] Test: POST /api/nodes/1/repos — replaces existing assignment of same type
- [ ] Test: POST /api/nodes/9999/repos — 404 device not found
- [ ] Test: POST /api/nodes/1/repos with repo_id=9999 — 404 repo not found
- [ ] Tests in `tests/integration/test_repo_api.py`
- [ ] Override `get_db` to use SQLite in-memory

**Blocked by**: TASK-019, TASK-020
**Blocks**: None

---

## Task Summary

| Sprint | Tasks | Total Estimate |
|--------|-------|----------------|
| Sprint 1: Device Data Layer & Discovery | TASK-001 to TASK-006 | 6h |
| Sprint 2: Device REST API | TASK-007 to TASK-008 | 1.5h |
| Sprint 3: Device Events | TASK-009 to TASK-012 | 4h |
| Sprint 4: Repository Data Layer & Scanner | TASK-013 to TASK-016 | 6h |
| Sprint 5: Repository REST API & Assignments | TASK-017 to TASK-020 | 4.5h |
| Sprint 6: Tests | TASK-021 to TASK-026 | 9.5h |
| **Total** | **26 tasks** | **31.5h** |
