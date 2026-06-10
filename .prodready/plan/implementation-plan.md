# Implementation Plan

## Overview

**Project**: IoT Device Discovery Service
**Pattern**: Single-Process Event-Driven Service
**Stack**: Python 3.13, FastAPI, SQLAlchemy 2.x, MySQL, pydantic-settings

## Architecture Summary

Single Python process with three concurrent concerns:
1. **UDP Message Ingestion** — `message_listener` receives broadcasts, handler pushes to thread-safe queue
2. **Background Worker** — daemon thread drains queue, cache check → DB upsert → cache update
3. **REST API** — FastAPI serves device, event, repo, and assignment endpoints via uvicorn

Plus one standalone process:
4. **Repository Scanner** — periodic Python script walks `/upgrades`, computes SHA256, syncs to DB

Existing codebase has: `app/` package, config, DB session, auth, `device_scaner.py` entry point.

## Phases

### Sprint 1: Device Data Layer & Discovery Engine

**Goal**: Device model in DB, CRUD, message handler with queue + worker + cache.

| Task | Description |
|------|-------------|
| TASK-001 | Device SQLAlchemy model + unique constraint |
| TASK-002 | Device Pydantic schemas (Create, Response) |
| TASK-003 | Device CRUD (get, list, create with IntegrityError handling) |
| TASK-004 | Message handler — extract chip_id/node, push to queue |
| TASK-005 | Discovery worker — queue drain, cache check, DB upsert |
| TASK-006 | Wire handler + worker into device_scaner.py startup |

### Sprint 2: Device REST API

**Goal**: Frontend can browse discovered devices via paginated REST API.

| Task | Description |
|------|-------------|
| TASK-007 | FastAPI REST server with device list endpoint |
| TASK-008 | Single device by ID endpoint |

### Sprint 3: Device Events

**Goal**: Store and retrieve logged events per device (upsert pattern, JSON parameters).

| Task | Description |
|------|-------------|
| TASK-009 | DeviceEvent SQLAlchemy model + composite unique constraint |
| TASK-010 | DeviceEvent Pydantic schemas (Create, Response) |
| TASK-011 | DeviceEvent CRUD (upsert by device_id+event_type, get, list) |
| TASK-012 | Event API endpoints (get single event, list events by device) |

### Sprint 4: Repository Data Layer & Scanner

**Goal**: Repository models, hash scanner script, repo CRUD.

| Task | Description |
|------|-------------|
| TASK-013 | Repository + RepositoryFile SQLAlchemy models |
| TASK-014 | Repository Pydantic schemas (Create, Response with nested files) |
| TASK-015 | Repository CRUD (create, list by type, file upsert, file cleanup) |
| TASK-016 | Repo scanner standalone script — walk /upgrades, SHA256, sync DB |

### Sprint 5: Repository REST API & Assignments

**Goal**: Frontend can browse repos and assign them to nodes.

| Task | Description |
|------|-------------|
| TASK-017 | NodeRepository model + schemas |
| TASK-018 | NodeRepository CRUD (assign with replace, list assignments) |
| TASK-019 | Repo list endpoint (GET /api/repos?type=...) |
| TASK-020 | Repo assignment endpoint (POST /api/nodes/{device_id}/repos) |

### Sprint 6: Tests

**Goal**: Full test coverage for all features.

| Task | Description |
|------|-------------|
| TASK-021 | Unit tests — message handler parsing, cache logic |
| TASK-022 | Unit tests — device CRUD operations |
| TASK-023 | Unit tests — event model, schemas, CRUD |
| TASK-024 | Unit tests — repo scanner logic |
| TASK-025 | Integration tests — device + event API endpoints |
| TASK-026 | Integration tests — repo + assignment API endpoints |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `message_listener` / `iot_message` API changes | High — handler breaks | External packages, no control. Pin versions if possible. Tests use mocks. |
| Cache cold start after restart — DB gets duplicate queries | Medium — brief DB load spike | DB unique constraint is final guard. Cache re-populates as messages arrive. |
| Unbounded queue growth under sustained flood | Medium — memory pressure | MVP scale is "hundreds of devices". Queue holds parsed tuples, not raw messages. Monitor and add backpressure in future. |
| MySQL connection issues in dev | Low — blocks local dev | Integration tests use SQLite in-memory. Dev can fallback to SQLite via env var. |
| `/upgrades` folder structure malformed | Low — scanner produces wrong data | Scanner logs errors per file and continues. Constitution: "hash must match actual file." |
| Scanner runs while API writes repos | Low — inconsistent reads | Same DB with proper transactions. Reads are consistent within a transaction. |

## Dependencies

External dependencies:
- [x] `message_listener` package — already available
- [x] `iot_message` package — already available
- [ ] MySQL database — needed for production, SQLite sufficient for dev/testing
- [x] `/upgrades` directory — filesystem path, mounted as Docker volume in scanner container
