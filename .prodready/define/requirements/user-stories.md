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

---

## Epic 4: Repository Management

### US-007: Scan Repository Files and Store Hashes
**As a** system operator
**I want to** a standalone script that scans `/upgrades` and calculates SHA256 hashes for all files
**So that** the database always has current file version information

**Acceptance Criteria**:
- [ ] Given the `/upgrades` directory contains repos with `_microplate` and/or `_userspace` subfolders, when the scanner runs, then SHA256 hashes are calculated for every file
- [ ] Given a file exists in a repo folder, when the scanner runs, then a record is created or updated with repo name, repo type, filename, and SHA256
- [ ] Given a file has been removed from disk, when the scanner runs, then the corresponding DB record is removed
- [ ] Given the scanner encounters a missing or unreadable file, when it processes the repo, then it logs the error and continues without crashing
- [ ] Given the scanner runs as a standalone script (not FastAPI), when it connects to the database, then it uses the same `DATABASE_URL` from config

**Priority**: P0
**Estimate**: M

---

### US-008: List Repositories by Type
**As a** frontend operator
**I want to** fetch repositories filtered by type (`_microplate` or `_userspace`)
**So that** I can see available repos with their files and hashes

**Acceptance Criteria**:
- [ ] Given repos exist in the database, when I GET `/api/repos?type=microplate`, then I receive a list of repos with name, type, and files (filename + SHA256)
- [ ] Given no repos match the requested type, when I GET `/api/repos?type=userspace`, then I receive an empty list
- [ ] Given an invalid type is requested, when I GET `/api/repos?type=invalid`, then a 400 error is returned

**Priority**: P0
**Estimate**: S

---

### US-009: Assign Repository to Node
**As a** frontend operator
**I want to** assign a microplate repo and/or userspace repo to a discovered node
**So that** I know which software version each node should run

**Acceptance Criteria**:
- [ ] Given a node exists and a repo of the requested type exists, when I assign the repo to the node, then the assignment is stored in the database
- [ ] Given a node already has a microplate repo assigned, when I assign a different microplate repo, then the old assignment is replaced
- [ ] Given a node has no userspace repo, when I assign a userspace repo, then the assignment is created
- [ ] Given a repo is assigned to multiple nodes, when I query the assignment, then all node-repo links are correct
- [ ] Given a non-existent node or repo ID, when I attempt assignment, then a 404 error is returned

**Priority**: P0
**Estimate**: S
