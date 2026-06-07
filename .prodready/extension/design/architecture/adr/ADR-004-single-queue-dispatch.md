# ADR-004: Single Queue with Tagged Items for Event Processing

## Status
Accepted

## Date
2026-06-07

## Context
The existing `MessageHandler` uses a single `queue.Queue` of `(chip_id, node)` tuples, drained by one worker thread. The extension needs to also queue event data — `(chip_id, node, event_type, parameters)` — which has a different shape.

## Decision
We will extend the existing queue to carry tagged items — either `("device", chip_id, node)` or `("event", chip_id, node, event_type, parameters)` — and dispatch in the worker loop based on the tag.

## Consequences

### Positive
- One worker thread, one queue — minimal complexity
- No new threading model to reason about
- Device discovery and event processing share the same DB session lifecycle
- Fast to implement — ~30 lines of change in existing handler

### Negative
- Queue now carries heterogeneous items — type annotation must use `tuple` union
- If event processing is slower than device discovery, it blocks both (unlikely at current scale)
- Worker loop has two code paths — slightly more complex than single-purpose loop

### Risks
- **Risk**: Large event parameters (e.g., hash of many files) could slow queue throughput.
  **Mitigation**: Parameters are JSON dicts — typical pong payload is ~200 bytes. Hash payloads are bounded by device firmware.

## Alternatives Considered
1. **Separate queue + worker for events**: More isolation, but adds a second thread, second queue, and coordination complexity. Rejected — overkill for solo dev at current scale.
2. **Wrap everything in a dataclass**: Cleaner types, but requires refactoring existing working code. Rejected — tagged tuple is simpler and matches existing pattern.
