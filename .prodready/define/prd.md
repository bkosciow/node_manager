# Product Requirements Document (PRD)

## 1. Executive Summary

**Product**: IoT Device Discovery Service
**Problem**: IoT devices send a flood of UDP broadcast messages, and there's no service to reliably discover and deduplicate them before storing in a database.
**Solution**: A lightweight service that listens for incoming device messages, extracts `(chip_id, node)` pairs, deduplicates via an in-memory cache (with DB unique constraint as final guard), and exposes a REST API for the frontend to browse discovered devices.
**Target Users**: Single operator (solo developer). Frontend app is the API consumer.
**Success Metric**: Zero duplicates in the database.

## 2. Goals & Non-Goals

### Goals
- Discover IoT devices from UDP message stream and store unique `(chip_id, node)` pairs
- Protect the database from duplicate writes during message floods via in-memory cache
- Expose paginated REST API for the frontend to list and inspect devices

### Non-Goals
- Real-time monitoring or device status tracking
- Multi-tenancy or user isolation
- API authentication (internal network only)
- Persistent cache across restarts

## 3. User Personas

### Persona: Operator (Solo Developer)
- **Context**: Runs IoT devices on a local network, needs to discover what's out there
- **Pain Point**: Manual device discovery is tedious; message flood overwhelms the DB with duplicates
- **Desired Outcome**: Fire and forget — service runs in the background, frontend shows a clean list of devices

## 4. Functional Requirements

### FR-1: Message Ingestion
- Receive UDP broadcast messages via existing `message_listener` infrastructure
- Parse `message.data` dict, extract `chip_id` (str) and `node` (str)
- Skip messages with missing fields or `None` data (log and continue)
- **Acceptance**: Valid messages produce device records; invalid messages are silently absorbed

### FR-2: Device Discovery & Deduplication
- Check in-memory cache for `(chip_id, node)` pair before any DB access
- On cache miss: query DB for existing record; if not found, insert new `Device`
- On cache hit: skip DB entirely
- DB enforces uniqueness via composite unique constraint on `(chip_id, node)`
- **Acceptance**: No duplicates in DB under any load

### FR-3: Device REST API
- `GET /api/devices` — paginated list (`skip`, `limit` params, `limit` max 1000)
- `GET /api/devices/{device_id}` — single device by ID (404 if missing)
- Response model: `id`, `chip_id`, `node`, `created_at`
- All endpoints protected by existing `verify_token` pattern (graceful skip when `API_TOKEN` is empty)
- **Acceptance**: Frontend can browse all devices with pagination

### FR-4: Repository Hash Scanning
- Standalone Python script walks `/upgrades/{repo_name}/{_microplate|_userspace}/` directories
- Calculate SHA256 for each file, store/update in `RepositoryFile` table
- Remove DB records for files no longer present on disk
- Repo name and type derived from folder structure
- **Acceptance**: Every file in `/upgrades` has a current hash in DB after each scan run

### FR-5: Repository REST API
- `GET /api/repos?type={microplate|userspace}` — list repos by type with files and hashes
- All endpoints protected by existing `verify_token` pattern
- **Acceptance**: Frontend can browse available repos with file version info

### FR-6: Repo-to-Node Assignment
- Assign one microplate repo and/or one userspace repo per node
- Same repo can be assigned to multiple nodes
- Replacing an assignment of the same type removes the old one
- **Acceptance**: Frontend can manage which software version each node should run

## 5. Non-Functional Requirements

- **Performance**: In-memory cache handles message flood; DB touched only for new devices
- **Reliability**: Service recovers gracefully from DB constraint violations (no crashes)
- **Hash accuracy**: Stored SHA256 must match actual file on disk — this is the core value of the repo feature
- **Deployment**: Local dev via Python venv (`.venv`), production TBD; scanner runs in separate Docker container with `/upgrades` volume
- **Budget**: Self-hosted, zero cost

## 6. Data Model Summary

### Entities
- **Device**: `id` (PK), `chip_id` (str), `node` (str), `created_at` (datetime)
- **Repository**: `id` (PK), `name` (str), `repo_type` (str — "microplate" or "userspace"), `created_at` (datetime)
- **RepositoryFile**: `id` (PK), `repository_id` (FK), `filename` (str), `sha256` (str), `updated_at` (datetime)
- **NodeRepository**: `id` (PK), `device_id` (FK), `repository_id` (FK), `repo_type` (str), `assigned_at` (datetime)

### Key Relationships
- Repository 1:N RepositoryFile (cascade delete)
- Device 1:0..2 NodeRepository (one per type)
- Repository 1:N NodeRepository (same repo → many nodes)

### Indexes
- `(chip_id, node)` — unique composite on Device
- `(name, repo_type)` — unique composite on Repository
- `(repository_id, filename)` — unique composite on RepositoryFile
- `(device_id, repo_type)` — unique composite on NodeRepository

## 7. Scope & Timeline

- **MVP Features**: Message ingestion, device discovery with cache dedup, paginated device list API, single device API, repository file hash scanning, repo listing by type, repo-to-node assignment
- **Future Features**: Device delete API, last-seen tracking, persistent cache, API authentication, change detection in repo files
- **Timeline**: No hard deadline
- **Team**: Solo developer

## 8. Open Questions & Risks

- Message volume is described as "flood" but not quantified — cache eviction strategy is TBD if device count grows unbounded
- Production deployment target is unspecified
- The `message_listener` and `iot_message` packages are external — API changes in those packages could break the handler
- Scanner schedule is TBD — how often should it run? (cron interval not specified)
- `/upgrades` folder structure is assumed to be well-formed — scanner behavior for malformed paths is TBD

## 9. References

- Detailed user stories: `requirements/user-stories.md`
- Data model: `data-model/entities.md`, `data-model/models.py`
- Test scenarios: `test-scenarios/device-discovery.feature`, `test-scenarios/device-api.feature`, `test-scenarios/repository-management.feature`
- Constraints: `constraints.md`
