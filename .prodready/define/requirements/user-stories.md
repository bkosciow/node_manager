# User Stories

## Epic 1: Message Ingestion & Device Discovery

### US-001: Process Incoming Device Messages
**As a** device discovery service
**I want to** parse incoming UDP messages and extract device identifiers
**So that** new devices can be identified and stored

**Acceptance Criteria**:
- [ ] Given a valid message with `chip_id` and `node` in `message.data`, when the handler processes it, then both fields are extracted correctly
- [ ] Given a message with missing `chip_id` or `node`, when the handler processes it, then the message is logged and skipped
- [ ] Given a `None` message or `None` data, when the handler processes it, then no exception is raised

**Priority**: P0
**Estimate**: S

---

### US-002: In-Memory Deduplication Cache
**As a** device discovery service
**I want to** check an in-memory cache before querying the database
**So that** the database isn't hammered during message floods

**Acceptance Criteria**:
- [ ] Given a `(chip_id, node)` pair exists in the cache, when a message arrives with the same pair, then no database query is executed
- [ ] Given a `(chip_id, node)` pair does NOT exist in the cache, when a message arrives, then the database is queried for an existing record
- [ ] Given a `(chip_id, node)` pair is found in the database but not in the cache, when the check completes, then the pair is added to the cache

**Priority**: P0
**Estimate**: S

---

### US-003: Store New Devices
**As a** device discovery service
**I want to** save newly discovered devices to the database
**So that** they are available through the API

**Acceptance Criteria**:
- [ ] Given a `(chip_id, node)` pair does not exist in the database, when processing completes, then a new device record is inserted
- [ ] Given a `(chip_id, node)` pair already exists in the database, when processing completes, then no new record is inserted
- [ ] Given a unique constraint violation on insert, when processing completes, then the error is handled gracefully (no crash)

**Priority**: P0
**Estimate**: S

---

## Epic 2: Device API

### US-004: List Devices (Paginated)
**As a** frontend operator
**I want to** fetch a paginated list of all discovered devices
**So that** I can browse devices without overwhelming the UI

**Acceptance Criteria**:
- [ ] Given devices exist in the database, when I GET `/api/devices`, then I receive a JSON array of devices with `id`, `chip_id`, `node`, and `created_at`
- [ ] Given more devices than the page size, when I GET `/api/devices?skip=10&limit=5`, then I receive at most 5 devices starting from offset 10
- [ ] Given no devices exist, when I GET `/api/devices`, then I receive an empty array
- [ ] Given `limit` exceeds 1000, when I GET `/api/devices`, then a 422 error is returned

**Priority**: P0
**Estimate**: S

---

### US-005: Get Single Device
**As a** frontend operator
**I want to** fetch a single device by its ID
**So that** I can view device details

**Acceptance Criteria**:
- [ ] Given a device with the requested ID exists, when I GET `/api/devices/{device_id}`, then I receive the device details
- [ ] Given no device matches the requested ID, when I GET `/api/devices/{device_id}`, then a 404 response is returned

**Priority**: P1
**Estimate**: S

---

## Epic 3: Integration

### US-006: Handler Registration with Message Listener
**As a** system operator
**I want to** the device discovery handler registered with the message listener
**So that** incoming messages are automatically processed

**Acceptance Criteria**:
- [ ] Given the scanner service starts, when the message listener initializes, then the `MessageHandler` from `device_discovery.py` is registered
- [ ] Given the handler is registered, when a UDP broadcast message arrives, then `handle()` is invoked with the parsed message

**Priority**: P0
**Estimate**: S
