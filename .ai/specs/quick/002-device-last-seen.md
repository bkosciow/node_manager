# 002 — Device last_seen_at / last_updated_at

**Status:** done (code + tests) — existing-DB ALTER superseded by the SPEC-005 migration
**Date:** 2026-11-12
**Size:** S (field addition, no architectural decisions)

## Context

`Device` only carries `created_at` (first discovery). The discovery dedupe
path (`device_discovery._process`) silently drops repeat pings — no
timestamp is refreshed, so "when was this node last seen" is not
answerable. `DeviceEvent.updated_at` is a partial proxy, but it only
covers the three supported event types and requires a per-request
aggregation.

## What to do

Add two columns to `Device` and return both from the device endpoints:

1. **`last_seen_at`** (NOT NULL, `default=utcnow`) — refreshed on **every**
   discovery message. The dedupe cache stays as the "is the device known?"
   fast path, but a cache hit now issues an UPDATE instead of skipping the
   DB entirely. New inserts get the column default.
2. **`last_updated_at`** (nullable) — set when a supported event is
   upserted for the device (`_process_event` → `touch_last_updated`).
   `None` until the device's first event.

Plumbing:

- `app/crud/device.py` — new `touch_last_seen(db, chip_id, node)` (bulk
  UPDATE by pair, no-op when unknown) and `touch_last_updated(db,
  device_id)`; 2.0-style `update()` per `database/query-style`.
- `app/schemas/device.py` — both fields on `DeviceResponse` and
  `DeviceWithUpdates`.
- `app/rest_server.py` — `GET /api/devices` (list) and
  `GET /api/devices/{id}` (detail) return `last_seen_at` /
  `last_updated_at`.
- `app/message_handler/device_discovery.py` — `_process` calls
  `touch_last_seen` on cache hit and on DB hit; `_process_event` calls
  `touch_last_updated` after `upsert_event`.

## Existing-DB migration (SUPERSEDED — see SPEC-005)

> The manual `ALTER` below is no longer the procedure. SPEC-005 introduced
> an Alembic migration system: the `0001` baseline revision already carries
> `last_seen_at` / `last_updated_at`, and `run_migrations()` runs
> `alembic upgrade head` on every entrypoint at startup. Schema changes now
> ship as revisions (GUARDRAILS "Schema = versioned Alembic migrations").
> The `ALTER` is kept only as historical reference.

_(original manual path, for reference)_

`init_db()` used `create_all()` which only creates missing tables, so an
existing MySQL DB needs:

```sql
ALTER TABLE devices
  ADD COLUMN last_seen_at DATETIME NULL,
  ADD COLUMN last_updated_at DATETIME NULL;
UPDATE devices SET last_seen_at = created_at WHERE last_seen_at IS NULL;
```

No SQL file under `upgrades/` — that directory is scanned by
`repo_scanner` as node repository content and would get hashed/served.

## Implementation Checklist

- [x] Model: two columns on `Device`
- [x] CRUD: `touch_last_seen`, `touch_last_updated`
- [x] Schemas: fields on `DeviceResponse` + `DeviceWithUpdates`
- [x] Handler: `_process` / `_process_event` touch calls
- [x] API: list + detail endpoints return both fields
- [x] Unit tests: `test_device_crud.py` (new CRUD fns),
      `test_device_discovery.py` (cache-hit now refreshes last_seen),
      `test_device_api.py` (response fields)
- [x] `pytest tests/ -q` + flake8 clean
- [~] Existing-DB ALTER — SUPERSEDED by SPEC-005 (`0001` baseline carries
      both columns; `run_migrations()` applies it at startup)

## Review

- `last_seen_at` (NOT NULL, default `utcnow`) is refreshed on **every**
  discovery message: the dedupe cache no longer skips the DB, a cache hit
  now issues a bulk `UPDATE ... last_seen_at` for the pair. Fresh inserts
  take the column default.
- `last_updated_at` (nullable) is set only when a supported event is
  upserted (`_process_event` → `touch_last_updated`), i.e. the device has
  reported data. `None` until then.
- Both fields are returned from `GET /api/devices` (via `DeviceWithUpdates`)
  and `GET /api/devices/{id}` (hand-built dict).
- `touch_last_seen` / `touch_last_updated` are 2.0-style `update()` per
  `database/query-style` and are re-exported from the `app.crud` barrel.
- Existing-DB migration is a manual `ALTER TABLE` + backfill (no migration
  framework; `upgrades/` is node-repo data, not SQL).
