# Architecture Pattern

## Selected Pattern: Single-Process Event-Driven Service

## Rationale

Based on:
- **Deployment**: Local machine / LAN, solo operator, Docker containers
- **Scale**: Hundreds of devices, high-frequency UDP flood, ~10 repos
- **Team**: Solo developer, no ops overhead tolerance
- **Budget**: Zero cost, self-hosted

A single-process event-driven service was selected because:

1. **Simplicity** — one process, one DB connection pool, zero external infrastructure (no Redis, RabbitMQ, or message broker)
2. **Decoupled ingestion from processing** — UDP handler pushes parsed tuples onto a thread-safe queue and returns immediately; a background worker drains the queue at its own pace
3. **Fast API responses** — FastAPI/uvicorn runs on the event loop, serving HTTP requests independently of message processing
4. **Fits MVP scale** — no horizontal scaling needed; a single worker thread handles hundreds of devices comfortably

## Structure

```
┌───────────┐   UDP broadcast    ┌──────────────────┐
│ IoT Nodes  │ ──────────────────→ │  Message Handler  │
│ (flooding) │                     │  (parse + queue)  │
└───────────┘                     └────────┬─────────┘
                                           │ queue.put()
                                           ▼
                                    ┌──────────────┐
                                    │  Queue (std) │
                                    └──────┬───────┘
                                           │ drain
                                           ▼
                                    ┌──────────────┐
                                    │  Worker      │
                                    │  (daemon     │
                                    │   thread)    │
                                    └──────┬───────┘
                                           │
                            ┌──────────────┼──────────────┐
                            │ cache hit?   │  cache miss? │
                            ▼              ▼              ▼
                       (skip, no IO)  query DB      insert new
                                                    (IntegrityError
                                                     → rollback)
                                           │
┌──────────────┐   HTTP          ┌─────────┴──────────┐
│  Frontend    │ ────────────────→  FastAPI REST API   │ ─── query ──→ MySQL
│  (browser)   │   GET /api/*    │  (uvicorn loop)    │
└──────────────┘                 └────────────────────┘
```

## Component Breakdown

| Component | Module | Thread/Loop | Responsibility |
|-----------|--------|-------------|----------------|
| Message Handler | `app/message_handler/device_discovery.py` | UDP listener thread | Parse `message.data`, extract `(chip_id, node)`, validate, push to queue |
| Discovery Worker | `app/message_handler/device_discovery.py` | Daemon thread | Drain queue, cache check, DB upsert, cache update |
| In-Memory Cache | `app/message_handler/device_discovery.py` | Worker thread only | `set[tuple[str, str]]` — O(1) dedup, no locks needed |
| Device Model | `app/models/device.py` | — | SQLAlchemy `Device` with composite unique constraint |
| Device CRUD | `app/crud/device.py` | Worker + API threads | `get_device`, `get_device_by_pair`, `get_devices`, `create_device` |
| REST API | `app/rest_server.py` | uvicorn event loop | `GET /api/devices`, `GET /api/devices/{id}`, token auth |
| Repo Scanner | `repo_scanner.py` | Standalone process | Walk `/upgrades`, SHA256 hash, upsert `RepositoryFile` records |
| Config | `app/config.py` | — | `pydantic_settings.BaseSettings`, module-level `settings` singleton |

## Threading Model

- **UDP listener thread** (managed by `message_listener` package) → calls `handle()` → `queue.put()` (non-blocking, unbounded)
- **Worker thread** (daemon, started on app init) → `queue.get(timeout=0.5)` → process → loop (timeout enables graceful stop)
- **FastAPI/uvicorn** (main thread + worker pool) → serves HTTP requests independently
- **Cache**: single-writer, single-reader (the worker thread) — no lock needed
- **DB sessions**: each worker iteration creates its own session (create → use → close in finally)

## Startup Sequence

1. FastAPI startup event fires
2. DB engine created, tables ensured (`init_db()`)
3. Discovery worker instantiated, daemon thread started
4. Message handler registered with `message_listener`
5. Server ready

## Shutdown Sequence

1. FastAPI shutdown event fires
2. Worker stop event signaled
3. Worker drains remaining queue items (5s timeout)
4. DB sessions closed

## Key Decisions

- **Queue over direct DB calls** — handler never blocks on I/O; UDP flood cannot stall the listener
- **In-memory cache + DB constraint** — cache handles 99% of duplicates fast; DB constraint is the final safety net
- **No external message broker** — overkill for single-process, single-operator MVP
- **No async/await for worker** — `message_listener` uses threads; mixing threading + asyncio adds complexity for no gain at MVP scale

## Future Considerations

- **Cache eviction** — if device count grows unbounded, add LRU eviction or periodic DB-backed cache rebuild
- **Persistent cache** — survive restarts by loading recent devices into cache on startup
- **Horizontal scaling** — would require external queue (Redis/RabbitMQ) and shared cache (Redis SET)
- **Queue backpressure** — add maxsize to queue if sustained floods cause memory pressure
