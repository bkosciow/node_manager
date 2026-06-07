# ADR-006: Upsert Strategy for DeviceEvent

## Status
Accepted

## Date
2026-06-07

## Context
Each event type per device should have exactly one row — the latest value. On arrival, we need to insert if missing or update if exists. This is a classic upsert pattern.

## Decision
We will use SQLAlchemy's `insert().on_duplicate_key_update()` (MySQL `INSERT ... ON DUPLICATE KEY UPDATE`) to perform the upsert in a single query, leveraging the unique constraint on `(device_id, event_type)`.

## Consequences

### Positive
- Single query — atomic, no race condition between check and insert
- MySQL-native — efficient, no application-level retry logic needed
- Clean code — one CRUD function handles both insert and update paths

### Negative
- MySQL-specific syntax — if we migrate to PostgreSQL, must switch to `ON CONFLICT`
- Cannot easily detect "was this an insert or update?" in the same query (not needed for current requirements)

### Risks
- **Risk**: If unique constraint is dropped or altered, upsert silently becomes a regular insert.
  **Mitigation**: Constraint is enforced at DB level. If migration drops it, upsert fails with an error — visible in logs.

## Alternatives Considered
1. **Python-level check-then-insert/update**: Two queries, race condition window between them. Rejected — unsafe under concurrent access.
2. **Session.merge()**: SQLAlchemy's built-in merge requires a primary key. Rejected — we don't know the PK on insert, and merge is less explicit than `on_duplicate_key_update`.
3. **INSERT OR IGNORE + UPDATE**: Two queries, first inserts (ignores conflict), second updates. Rejected — two queries when one suffices.
