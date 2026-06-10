# ADR-002: In-Memory Cache for Deduplication

## Status
Accepted

## Date
2026-06-09

## Context

During message floods, the same `(chip_id, node)` pair arrives repeatedly. Without deduplication, each message triggers a DB query, overwhelming the database. The constitution states: "No duplicates in DB — enforced by unique constraint." The constraint is the final guard, but we need a fast first line of defense.

## Decision

We will use an **in-memory `set[tuple[str, str]]`** as the primary deduplication layer:

- **Cache hit** → skip DB entirely (O(1) lookup)
- **Cache miss** → query DB. If found, add to cache (warm). If not found, insert.
- **No eviction** — cache grows monotonically. At MVP scale (hundreds of devices), memory is negligible (~100 bytes per tuple).
- **No persistence** — cache is empty after restart. DB unique constraint handles the cold-start window.

The cache is accessed only by the worker thread (single writer, single reader), so no lock is needed.

## Consequences

### Positive
- **O(1) dedup** — set lookup is constant time; handles flood without DB I/O
- **Zero dependencies** — stdlib `set`, no Redis, no external cache server
- **Thread-safe by design** — single-thread access eliminates lock overhead and deadlock risk
- **Simple** — no cache invalidation, no TTL, no eviction policy to tune

### Negative
- **Cold start after restart** — cache is empty; DB gets queries for all recently seen pairs. Mitigated by DB unique constraint (final guard) and brief restart window
- **Unbounded growth** — cache never shrinks. At MVP scale this is acceptable (hundreds of tuples ≈ KB of memory)
- **No cross-process sharing** — if multiple scanner instances run, each has its own cache. Not a concern for single-operator deployment

### Risks
- **Device count grows to thousands** — cache memory becomes measurable. Mitigation: add LRU eviction or periodic DB-backed cache rebuild when scale increases
- **Restart during flood** — DB gets burst of queries. Mitigation: DB unique constraint prevents duplicates; brief burst is harmless

## Alternatives Considered

1. **DB-only dedup** (no cache) — rejected because every message triggers a DB query; under flood, DB becomes the bottleneck
2. **Redis SET** — rejected as overkill; adds infrastructure dependency, network latency, and ops overhead for a single-process service
3. **LRU cache with TTL** — rejected as premature optimization; adds complexity (eviction policy, TTL tuning) for no benefit at MVP scale since devices are persistent (not ephemeral)
4. **Persistent cache (disk)** — rejected as unnecessary; restart is rare, cold-start window is brief, DB constraint is the final guard
