# ADR-003: Database Deduplication via Unique Constraint

## Status
Accepted

## Date
2026-06-09

## Context

The constitution states: "No duplicates in DB — enforced by unique constraint on `(chip_id, node)` in the devices table. The in-memory cache is a performance optimization; the DB constraint is the final guard."

The in-memory cache handles the vast majority of duplicates, but it cannot guarantee uniqueness during cold start (cache is empty after restart), crashes, or future multi-process deployments. The database must enforce uniqueness as the final safety net.

## Decision

We will use a **composite unique constraint** on `(chip_id, node)` at the database level. Attempted duplicate inserts raise `IntegrityError`, which the worker catches and handles gracefully (rollback, log warning, add to cache, continue).

```python
class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("chip_id", "node", name="uq_chip_id_node"),
    )
```

Worker handling:
```python
try:
    create_device(db, DeviceCreate(chip_id=chip_id, node=node))
    self.cache.add((chip_id, node))
except IntegrityError:
    db.rollback()
    logger.warning("Duplicate insert prevented by DB constraint: %s/%s", chip_id, node)
    self.cache.add((chip_id, node))
```

## Consequences

### Positive
- **Hard guarantee** — database enforces uniqueness at all times, regardless of application state
- **Survives restarts and crashes** — constraint is a DB-level invariant, not application state
- **Standard SQL** — portable across MySQL (production) and SQLite (dev/testing)
- **Clear error signal** — `IntegrityError` means "already exists", easy to log and monitor

### Negative
- **Exception handling overhead** — worker must catch `IntegrityError` and rollback. At MVP scale this is rare (cache handles 99%+ of duplicates)
- **Race condition window** — if two worker threads insert simultaneously (not the case with single worker), one hits the constraint. Handling: catch error, log, add to cache, continue

### Risks
- **Frequent constraint violations** — would indicate cache is not working correctly. Mitigation: log warnings include pair; monitor log frequency
- **Constraint not created** — would allow duplicates. Mitigation: `create_all()` creates constraint on startup; integration tests verify constraint enforcement

## Alternatives Considered

1. **`INSERT ... ON DUPLICATE KEY UPDATE`** — rejected because MySQL syntax requires at least one UPDATE column; SQLite uses `INSERT OR IGNORE`. Different syntax per driver reduces portability. Silent success is harder to log/monitor.
2. **Application-level check only** (`SELECT` before `INSERT`) — rejected because of race condition window between SELECT and INSERT. No guarantee across crashes or restarts. Violates non-negotiable ("No duplicates in DB").
3. **Trigger-based dedup** — rejected as overkill. Triggers add complexity and are harder to debug. Unique constraint is the standard, well-understood approach.
