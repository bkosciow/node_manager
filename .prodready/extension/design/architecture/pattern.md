# Architecture Pattern — Event Data Extension

## Selected Pattern: Monolith Extension (In-Process)

## Rationale
Based on:
- Deployment: same Docker container, same process
- Scale: ~10-50 devices, events every few seconds
- Team: solo developer

The existing monolith was extended because:
- The event handler runs in the same process as device discovery — zero inter-process overhead
- Shared database session, shared queue, shared worker thread
- No new deployment surface, no new container, no new service

## Structure

```
Incoming UDP message
        │
        ▼
  message_listener (existing)
        │
        ▼
  MessageHandler.handle() (extended)
        │
        ├─► Extract (chip_id, node) ──► queue.put(("device", chip_id, node))
        │
        └─► Detect event_type ────────► queue.put(("event", chip_id, node, event_type, parameters))
                                          │
                                          ▼
                                    Worker thread (existing, extended)
                                          │
                                    ┌─────┴─────┐
                                    │  dispatch  │
                                    └─────┬─────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
              (chip_id, node)     (chip_id, node,            (chip_id, node,
              exists?             event_type,                 event_type,
              ──► upsert          parameters)                 parameters)
              Device              ──► upsert                  ──► upsert
                                  DeviceEvent                 DeviceEvent
                                  (system.pong)               (system.*.hash)
```

## Key Decisions
- **Single tagged queue** — items are tuples: `("device", chip_id, node)` or `("event", chip_id, node, event_type, parameters)`. Worker dispatches on tag.
- **Auto-create device** — if event arrives for unknown device, create it first (same logic as discovery, just triggered from event path).
- **Upsert via SQLAlchemy** — `insert().on_duplicate_key_update()` for MySQL, one query per event.

## Future Considerations
- If event volume grows (>100 devices, >1 event/sec/device), consider separate worker thread for events
- If historical tracking is needed, switch from upsert to append-only with partitioned table
