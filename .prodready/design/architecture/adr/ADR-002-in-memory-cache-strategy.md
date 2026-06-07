# ADR-002: In-Memory Cache Strategy

**Status**: Accepted
**Date**: 2026-06-07
**Context**: IoT Device Discovery Service

## Problem

During message floods, the same `(chip_id, node)` pair arrives repeatedly. We need an in-memory cache to avoid hammering the database with duplicate checks. The cache strategy must balance simplicity, memory usage, and correctness.

## Options Considered

### Option A: Unbounded Set (CHOSEN)
Plain Python `set[tuple[str, str]]`. Each unique device pair is added once. No eviction.

**Pros**: O(1) lookup and insert. Zero complexity. Memory cost is minimal — each tuple is ~100 bytes. 1000 devices = ~100 KB. No TTL management, no eviction logic.
**Cons**: Grows with unique device count. On service restart, cache is cold (all messages hit DB until re-populated). Mitigation: DB unique constraint handles cold start safely.

### Option B: TTL-Based Cache
Entries expire after N minutes. On expiry, cache misses fall through to DB check.

**Pros**: Bounded memory if devices churn (appear/disappear). Handles restart more gracefully (less cold start impact if TTL < uptime).
**Cons**: Adds complexity (TTL tracking, cleanup thread). For our use case, devices are persistent — a discovered device stays discovered. TTL provides no benefit.

### Option C: LRU Cache
`functools.lru_cache` or `CacheControl` with max size.

**Pros**: Bounded memory
**Cons**: Evicts known devices — subsequent messages for evicted devices hit DB unnecessarily. Devices are static (not ephemeral), so eviction is counterproductive.

## Decision

**Option A: Unbounded Set** — `set[tuple[str, str]]`.

## Consequences

### Positive
- Simplest possible implementation — one `set.add()` and one `in` check
- O(1) operations, no locks needed (single-threaded worker accesses it)
- Memory is negligible at MVP scale (hundreds of devices)
- No configuration needed (no TTL, no max size)

### Negative
- Cold start after restart: cache is empty, all messages hit DB briefly. Mitigation: DB unique constraint on `(chip_id, node)` prevents duplicates. Cache re-populates as messages arrive.
- Unbounded growth if device count grows to millions. Mitigation: MVP scale is hundreds. Add LRU or persistence in future if needed.

## Implementation Notes

```python
self.cache: set[tuple[str, str]] = set()

# In worker:
key = (chip_id, node)
if key in self.cache:
    return  # skip DB entirely

# DB check + insert
existing = get_device_by_pair(db, chip_id, node)
if existing is None:
    create_device(db, DeviceCreate(chip_id=chip_id, node=node))
    self.cache.add(key)
else:
    self.cache.add(key)  # warm cache from DB hit
```
