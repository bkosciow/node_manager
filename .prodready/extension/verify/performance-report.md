# Performance Report — Event Data Extension

Generated: 2026-06-07

## Test Performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Full suite (77 tests) | 2.44s | < 10s | ✓ Pass |
| Unit tests (59) | ~1s | < 5s | ✓ Pass |
| Integration tests (18) | ~1.4s | < 5s | ✓ Pass |

## Worker Performance

- Single-threaded, tagged queue — no thread coordination overhead
- Each event processed in one DB session (open → upsert → close)
- In-memory cache for device discovery prevents duplicate DB queries
- Event upsert: one query for get_event + one for insert/update = 2 queries max

## Database

| Check | Status |
|-------|--------|
| Unique constraint on (device_id, event_type) | ✓ |
| FK with CASCADE delete | ✓ |
| JSON column for parameters (native MySQL JSON) | ✓ |
| No N+1 queries (single query per operation) | ✓ |

## Docker

| Check | Status |
|-------|--------|
| Multi-stage build (3 stages) | ✓ |
| Non-root user | ✓ |
| Health check | ✓ |
| Image size: lean (python:3.13-slim base) | ✓ |

## Optimization Recommendations

1. **Future**: If event volume grows (>100 devices, >1 event/sec), consider batching upserts
2. **Future**: If historical tracking is needed, switch to append-only with periodic cleanup

## Result

**Status: PASSED — all targets met**
