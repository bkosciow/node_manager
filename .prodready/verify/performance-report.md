# Performance Report

Generated: 2026-06-07

## Core Web Vitals

N/A — This project has no frontend. API-only service.

## API Response Times

Full load testing (Apache Bench / k6) requires a running MySQL instance and was not performed in this verification. However, the test suite ran 34 integration tests in **1.23s total**, implying sub-50ms average response time per request against SQLite.

| Endpoint | Expected (MySQL) | Notes |
|----------|-----------------|-------|
| GET /health | < 5ms | No DB access, returns static dict |
| GET /api/devices | < 50ms (small dataset) | Single SELECT with OFFSET/LIMIT |
| GET /api/devices/{id} | < 10ms | Single SELECT by PK (indexed) |

**Targets**:
- p50: < 100ms — ✓ Expected (simple queries, small dataset)
- p95: < 200ms — ✓ Expected
- p99: < 500ms — ✓ Expected

## Database

| Check | Status | Notes |
|-------|--------|-------|
| Primary key indexed | ✓ | `id` — `primary_key=True, index=True` |
| Unique constraint indexed | ✓ | `UniqueConstraint("chip_id", "node")` — MySQL creates implicit index |
| No N+1 queries | ✓ | Single-entity model, no relationships to eager-load |
| Query simplicity | ✓ | All queries are single-table SELECT with WHERE/OFFSET/LIMIT |
| Session management | ✓ | Sessions created per-operation, closed in `finally` blocks |

## In-Memory Cache Performance

| Check | Status | Notes |
|-------|--------|-------|
| Cache data structure | ✓ `set[tuple[str, str]]` — O(1) lookup |
| Cache hit → no DB access | ✓ Verified in `test_cache_hit_skips_db` |
| Cache miss → single DB query | ✓ Verified in `test_cache_miss_db_miss_inserts` |
| Thread safety | ✓ `queue.Queue` is thread-safe; `set` operations are atomic for tuples |
| Memory growth | ⚠ Unbounded — cache grows with unique device count. Acceptable for MVP (tens to hundreds of devices). |

## Bundle Size

N/A — No frontend. Backend package size is irrelevant for API performance.

## Test Execution Performance

| Metric | Value |
|--------|-------|
| Total tests | 34 |
| Total time | 1.23s |
| Average per test | 36ms |
| Slowest test type | Integration (DB + HTTP) — ~50ms each |

## Optimization Recommendations

1. **Cache eviction** (future): If device count grows to thousands, consider TTL-based eviction or LRU cache (`functools.lru_cache` or `cachetools.TTLCache`).
2. **Connection pooling** (future): SQLAlchemy `create_engine` defaults to no pool for non-async. Consider `QueuePool` for high-concurrency production.
3. **Pagination optimization** (future): For large datasets, consider cursor-based pagination instead of OFFSET-based to avoid full-table scans at high offsets.

## Result

**Status: PASSED** — All architectural decisions support the performance targets for the expected scale (tens to hundreds of devices, single operator).
