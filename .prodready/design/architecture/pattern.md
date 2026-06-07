# Architecture Pattern

## Pattern: Event-Driven Service with Background Worker

### Overview

The service runs two concurrent concerns within a single Python process:

1. **UDP Message Ingestion** — `message_listener` package receives UDP broadcasts and invokes our handler. The handler pushes parsed messages onto a thread-safe queue (non-blocking).
2. **Background Worker** — A daemon thread drains the queue, performs cache check → DB query → insert, and updates the in-memory dedup cache.
3. **REST API** — FastAPI serves `GET /api/devices` and `GET /api/devices/{id}` on a separate thread pool (uvicorn event loop).

```
┌─────────────┐     UDP      ┌──────────────┐    put()    ┌──────────┐    process    ┌──────────┐
│ IoT Devices │ ────────────→ │  Handler     │ ──────────→ │  Queue   │ ────────────→ │  Worker  │
│ (broadcast) │               │ (push only)  │              │ (thread-  │                │ (daemon) │
└─────────────┘               └──────────────┘              │  safe)   │                └──────────┘
                                                            └──────────┘                   │
                                                                                           │
                                                                                     cache check →
                                                                                     DB query →
                                                                                     insert
                                                                                           │
┌─────────────┐     HTTP      ┌──────────────┐     query      ┌──────────┐                │
│  Frontend   │ ────────────→ │  FastAPI     │ ─────────────→ │ MySQL    │ ←──────────────┘
│  (browser)  │               │  REST Server │                │ Database │
└─────────────┘               └──────────────┘                └──────────┘
```

### Component Responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| Message Handler | `app/message_handler/device_discovery.py` | Parse message, extract `(chip_id, node)`, push to queue |
| Discovery Worker | `app/message_handler/device_discovery.py` | Drain queue, cache check, DB upsert, cache update |
| In-Memory Cache | `app/message_handler/device_discovery.py` | `set[tuple[str, str]]` — O(1) dedup lookup |
| Device Model | `app/models/device.py` | SQLAlchemy `Device` model |
| Device CRUD | `app/crud/device.py` | `get_device`, `get_devices`, `create_device` |
| Device Schema | `app/schemas/device.py` | Pydantic `DeviceCreate`, `DeviceResponse` |
| REST API | `app/rest_server.py` | Existing FastAPI app, add device routes |
| Config | `app/config.py` | `NODE_LISTENER_*`, `DATABASE_URL`, existing settings |

### Threading Model

- **UDP listener thread** (managed by `message_listener` package) → calls `handle()` → `queue.put()` (non-blocking, maxsize=0 = unbounded)
- **Worker thread** (daemon, started on app init) → `queue.get()` → process → loop
- **FastAPI/uvicorn** (main thread + worker pool) → serves HTTP requests independently
- **Shared state**: the cache `set` is only written by the worker thread and only read by the worker thread — no lock needed (single writer, single reader = the worker itself)

### Startup Sequence

1. FastAPI startup event fires
2. DB engine created, tables ensured (`init_db()`)
3. Discovery worker instantiated with queue reference
4. Worker daemon thread started
5. Handler registered with `message_listener`
6. Server ready

### Shutdown Sequence

1. FastAPI shutdown event fires
2. Worker thread signaled to stop (event flag)
3. Worker drains remaining queue items (graceful, timeout 5s)
4. DB session closed

### Why This Pattern

- **Decouples ingestion from processing** — handler never blocks on DB, UDP messages are never dropped during DB slowdowns
- **Simple** — one process, one queue, one worker thread. No external message broker (Redis, RabbitMQ)
- **Fits MVP scale** — hundreds of devices, single operator, no horizontal scaling needed
- **Low latency for API** — FastAPI runs independently, API responses are fast DB queries unaffected by message processing

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| Sync handler (process in callback) | Handler blocks during DB writes; UDP flood could backlog the listener |
| Batch inserts with buffer | More complex, unnecessary for MVP scale |
| External queue (Redis/RabbitMQ) | Overkill for single-process, single-operator MVP |
| Async/await with asyncio queue | `message_listener` uses threads; mixing threading + asyncio adds complexity |
