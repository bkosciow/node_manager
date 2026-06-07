# ADR-003: Database Deduplication Strategy

**Status**: Accepted
**Date**: 2026-06-07
**Context**: IoT Device Discovery Service

## Problem

We must guarantee zero duplicate devices in the database. The in-memory cache is a performance optimization, not a guarantee (cold start, crashes, future multi-process). We need a database-level enforcement strategy.

## Options Considered### Option A: Composite Unique Constraint (CHOSEN)
`UNIQUE (chip_id, node)` at the database level. Attempted duplicate inserts raise an integrity error that the application handles gracefully.

**Pros**: Database-enforced — impossible to have duplicates regardless of application state. Works across restarts, crashes, and future multi-process deployments. Standard SQL, zero overhead on reads.
**Cons**: Duplicate inserts raise `IntegrityError` — must catch and handle. Race condition possible if two worker threads insert simultaneously (not an issue with single worker, but good to handle anyway).

### Option B: INSERT ... ON DUPLICATE KEY UPDATE / INSERT OR IGNORE
Silent upsert — duplicate insert is a no-op.

**Pros**: No exception handling needed. Atomic at DB level.
**Cons**: MySQL syntax is `INSERT ... ON DUPLICATE KEY UPDATE` (requires at least one UPDATE column). SQLite uses `INSERT OR IGNORE`. Different syntax per driver — less portable. Silent success is harder to log/monitor.

### Option C: Application-Level Check Only
`SELECT` before `INSERT`. No DB constraint.

**Pros**: No exception handling
**Cons**: Race condition window between SELECT and INSERT. No guarantee across crashes or restarts. **Rejected** — violates non-negotiable ("No duplicates in DB").

## Decision

**Option A: Composite Unique Constraint** with graceful `IntegrityError` handling in application code.

## Consequences

### Positive
- Hard guarantee — database enforces uniqueness at all times
- Works correctly after cache cold start, crashes, restarts
- Standard SQL — portable across MySQL and SQLite (dev vs test)
- Clear error signal — `IntegrityError` means "already exists", easy to log

### Negative
- Worker must catch `sqlalchemy.exc.IntegrityError` and handle gracefully (rollback, log, continue)
- If we ever run multiple workers, concurrent inserts could both pass the cache check and one would hit the constraint. Handling: catch error, log warning, add to cache, continue.

## Implementation Notes

```python
# Model (SQLAlchemy):
class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("chip_id", "node", name="uq_chip_id_node"),
    )

# Worker:
from sqlalchemy.exc import IntegrityError

try:
    create_device(db, DeviceCreate(chip_id=chip_id, node=node))
    self.cache.add((chip_id, node))
except IntegrityError:
    db.rollback()
    logger.warning("Duplicate insert prevented by DB constraint: %s/%s", chip_id, node)
    self.cache.add((chip_id, node))
```
