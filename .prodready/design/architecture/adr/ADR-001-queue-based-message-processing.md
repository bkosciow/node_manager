# ADR-001: Queue-Based Message Processing

## Status
Accepted

## Date
2026-06-09

## Context

The device discovery handler receives UDP broadcast messages at high frequency ("flood"). Each message must be parsed, validated, deduplicated, and potentially stored in the database. The handler is invoked by the `message_listener` package on the UDP listener thread.

Processing a message involves I/O (DB query, potential insert). If the handler blocks during I/O, the UDP listener thread cannot receive new messages, causing message loss during floods.

## Decision

We will use a **thread-safe queue** (`queue.Queue`) to decouple message ingestion from processing:

1. **Handler** (UDP thread): parse message, extract `(chip_id, node)`, validate, push tuple to queue → return immediately
2. **Worker** (daemon thread): drain queue, check cache, query DB, insert if needed

The queue is unbounded (`maxsize=0`) so `put()` never blocks. The worker thread drains items at its own pace.

## Consequences

### Positive
- **Handler never blocks** — UDP listener can receive messages continuously, even during DB slowdowns
- **Simple** — stdlib `queue.Queue`, no external dependency, no message broker to operate
- **Backpressure-free** — during floods, queue grows in memory (tuples are tiny: two strings each)
- **Graceful shutdown** — worker drains remaining items on stop signal (5s timeout)

### Negative
- **Memory growth** — unbounded queue can grow under sustained flood. Mitigated by small payload size (tuple of two strings) and MVP scale (hundreds of devices, not millions of messages/sec)
- **Processing latency** — messages are not processed instantly; they wait in queue. Acceptable for device discovery (not real-time monitoring)

### Risks
- **Sustained flood exceeds worker throughput** — queue grows indefinitely. Mitigation: monitor queue size, add backpressure or maxsize in future if needed
- **Worker crashes** — unprocessed messages remain in queue. Mitigation: worker is a simple loop with broad exception handling; queue survives worker restart if worker is re-launched

## Alternatives Considered

1. **Sync handler (process in callback)** — rejected because handler blocks during DB writes; UDP flood could backlog the listener and drop messages
2. **Batch inserts with buffer** — rejected as overkill for MVP scale; adds complexity (buffer size, flush interval, partial failure handling)
3. **External queue (Redis/RabbitMQ)** — rejected as overkill for single-process, single-operator MVP; adds infrastructure dependency and ops overhead
4. **asyncio.Queue** — rejected because `message_listener` uses threads; mixing threading + asyncio adds complexity for no gain at MVP scale
