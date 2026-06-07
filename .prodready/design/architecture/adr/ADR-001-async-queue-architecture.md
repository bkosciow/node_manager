# ADR-001: Async Queue Architecture for Message Processing

**Status**: Accepted
**Date**: 2026-06-07
**Context**: IoT Device Discovery Service

## Problem

IoT devices send a high-volume flood of UDP broadcast messages. We need to process each message (parse, dedup, store) without blocking the UDP listener or dropping messages.

## Options Considered

### Option A: Synchronous Handler
Process each message directly in the `handle()` callback — cache check, DB query, insert, all inline.

**Pros**: Simple, no threading complexity, easy to debug
**Cons**: Handler blocks during DB writes. Under flood conditions, UDP listener backlogs. Risk of dropped messages.

### Option B: Async Queue (CHOSEN)
Handler pushes parsed messages onto a `queue.Queue`. A background daemon thread drains the queue and processes messages sequentially.

**Pros**: Handler never blocks (non-blocking `put()`). Decouples ingestion rate from processing rate. Simple (stdlib queue + threading). Graceful degradation under load.
**Cons**: Slight latency between message arrival and processing. Queue grows under sustained overload (unbounded). One moving part (worker thread) to debug.

### Option C: Batch Processing
Accumulate messages in a timed buffer, flush to DB in batches.

**Pros**: Maximum DB throughput, fewer transactions
**Cons**: More complexity (buffer management, flush timing, partial failures). Higher latency for device visibility. Overkill for MVP scale.

### Option D: External Message Broker
Use Redis/RabbitMQ as the queue.

**Pros**: Horizontal scaling, persistence, monitoring
**Cons**: External dependency, operational overhead. Overkill for single-operator MVP.

## Decision

**Option B: Async Queue** with `queue.Queue` + daemon thread.

## Consequences

### Positive
- Handler is fast — `queue.put()` is non-blocking and O(1)
- DB processing is isolated from UDP listener performance
- Simple implementation (~50 lines for worker + handler)
- No external dependencies beyond stdlib

### Negative
- Queue is unbounded — under extreme sustained flood, memory grows. Mitigation: MVP scale is "hundreds of devices" — queue holds parsed tuples, not raw messages. Monitor and add backpressure in future if needed.
- Worker thread is single-threaded — DB processing is sequential. Mitigation: sufficient for MVP. Parallelize later if DB becomes bottleneck.
- No persistence — messages in queue are lost on crash. Mitigation: DB unique constraint ensures idempotency. Redelivered messages are harmless (duplicate check).

## Implementation Notes

```python
import queue
import threading

class DeviceDiscoveryHandler(Handler):
    def __init__(self):
        self.queue: queue.Queue[Message] = queue.Queue(maxsize=0)  # unbounded
        self.cache: set[tuple[str, str]] = set()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)

    def start(self):
        self._worker_thread.start()

    def handle(self, message):
        # Non-blocking push — never drops messages
        self.queue.put(message)

    def _worker(self):
        while not self._stop_event.is_set():
            try:
                msg = self.queue.get(timeout=0.5)  # timeout allows stop check
                self._process(msg)
            except queue.Empty:
                continue

    def _process(self, message):
        # parse → cache check → DB query → insert → cache update
        ...
```
