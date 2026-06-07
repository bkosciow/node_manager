# Implementation Plan

## Overview

**Project**: IoT Device Discovery Service
**Pattern**: Event-Driven Service with Background Worker
**Stack**: Python, FastAPI, SQLAlchemy 2.x, MySQL, pydantic-settings

## Architecture Summary

Single Python process with three concurrent concerns:
1. **UDP Message Ingestion** — `message_listener` receives broadcasts, handler pushes to thread-safe queue
2. **Background Worker** — daemon thread drains queue, cache check → DB query → insert, updates dedup cache
3. **REST API** — FastAPI serves `GET /api/devices` and `GET /api/devices/{id}` via uvicorn

Existing codebase has: `app/` package, config, DB session, stub `MessageHandler`, `device_scaner.py` entry point.

## Phases

### Sprint 1: Data Layer & Discovery Engine

**Goal**: Device model in DB, CRUD operations, full message handler with queue + worker + cache.

| Task | Description |
|------|-------------|
| TASK-001 | Device SQLAlchemy model + unique constraint |
| TASK-002 | Device Pydantic schemas (Create, Response) |
| TASK-003 | Device CRUD (get, list, create with IntegrityError handling) |
| TASK-004 | Message handler — extract chip_id/node, push to queue |
| TASK-005 | Discovery worker — queue drain, cache check, DB upsert |
| TASK-006 | Wire handler + worker into device_scaner.py startup |

### Sprint 2: REST API

**Goal**: Frontend can browse discovered devices via paginated REST API.

| Task | Description |
|------|-------------|
| TASK-007 | FastAPI REST server with device list endpoint |
| TASK-008 | Single device by ID endpoint |

### Sprint 3: Tests

**Goal**: Full test coverage for discovery logic and API endpoints.

| Task | Description |
|------|-------------|
| TASK-009 | Unit tests — message handler parsing, cache logic |
| TASK-010 | Unit tests — CRUD operations |
| TASK-011 | Integration tests — device API endpoints |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `message_listener` / `iot_message` API changes | High — handler breaks | External packages, no control. Pin versions if possible. Tests use mocks. |
| Cache cold start after restart — DB gets duplicate queries | Medium — brief DB load spike | DB unique constraint is final guard. Cache re-populates as messages arrive. |
| Unbounded queue growth under sustained flood | Medium — memory pressure | MVP scale is "hundreds of devices". Queue holds parsed tuples, not raw messages. Monitor and add backpressure in future. |
| MySQL connection issues in dev | Low — blocks local dev | Integration tests use SQLite in-memory. Dev can fallback to SQLite via env var. |

## Dependencies

External dependencies:
- [x] `message_listener` package — already available
- [x] `iot_message` package — already available
- [ ] MySQL database — needed for production, SQLite sufficient for dev/testing
