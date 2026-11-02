# MessageHandler Tests (no DB required)

- `handle()` is tested with `MagicMock()` messages: set `m.data = {...}`
  (a dict), then assert on queue contents via
  `h.queue.qsize()` / `h.queue.get_nowait()`, comparing whole tuples.
- Event-detection coverage: each `SUPPORTED_EVENTS` type queues BOTH a
  `("device", …)` tuple and an `("event", …)` tuple; an unrecognized or
  missing `event` field queues only the device tuple; missing
  `parameters` defaults to `{}`.
- Worker dispatch is tested by replacing `h._process` / `h._process_event`
  with lambdas — no DB access in those tests.
- DB paths (`_process`, `_process_event`) are tested separately in
  `test_device_discovery.py` against a real file-based SQLite (see
  `unit-test-idiom` for why file-based, not in-memory).
