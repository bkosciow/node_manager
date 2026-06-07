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

## 5. Non-Functional Requirements

- **Performance**: In-memory cache handles message flood; DB touched only for new devices
- **Reliability**: Service recovers gracefully from DB constraint violations (no crashes)
- **Deployment**: Local dev via Python venv (`.venv`), production TBD
- **Budget**: Self-hosted, zero cost

## 6. Data Model Summary

### Entities
- **Device**: `id` (PK), `chip_id` (str), `node` (str), `created_at` (datetime)

### Key Relationships
None — single entity for MVP.

### Indexes
- `(chip_id, node)` — unique composite constraint (dedup enforcement)

## 7. Scope & Timeline

- **MVP Features**: Message ingestion, device discovery with cache dedup, paginated device list API, single device API
- **Future Features**: Device delete API, last-seen tracking, persistent cache, API authentication
- **Timeline**: No hard deadline
- **Team**: Solo developer

## 8. Open Questions & Risks

- Message volume is described as "flood" but not quantified — cache eviction strategy is TBD if device count grows unbounded
- Production deployment target is unspecified
- The `message_listener` and `iot_message` packages are external — API changes in those packages could break the handler

## 9. References

- Detailed user stories: `requirements/user-stories.md`
- Data model: `data-model/entities.md`, `data-model/models.py`
- Test scenarios: `test-scenarios/device-discovery.feature`, `test-scenarios/device-api.feature`
- Constraints: `constraints.md`
