# MessageHandler (device_discovery.py)

- `handle()` runs on the listener thread: parse + normalize + enqueue ONLY
  — no DB work in `handle()`.
- Queue items: `("device", chip_id, node)` always;
  `("event", chip_id, node, event_type, parameters)` only when
  `event_type ∈ SUPPORTED_EVENTS` (frozenset of protocol-defined types —
  see `database/event-hash-diff`).
- A daemon worker thread drains the queue; one short-lived `SessionLocal()`
  session per item, closed in `finally`.
- Dedup: in-memory `self.cache: set` (fast path) → DB lookup →
  `IntegrityError` (concurrent insert) = rollback + add to cache.
- Lazy imports: `app.db.session` / `app.crud.*` are imported inside worker
  methods, not at module import time — keep the handler importable standalone.
- Adding a new event type = extend the `SUPPORTED_EVENTS` frozenset.
  Protocol event-type strings are never renamed (GUARDRAILS BLOCK #1).
