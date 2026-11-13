# Integration Test Fixtures (tests/conftest.py)

- Integration tests use a **file-based** SQLite (`tempfile.mkdtemp()` →
  `sqlite:////path/test.db`), NOT in-memory. Reason: `TestClient` spawns
  a separate thread, so every connection (including the one TestClient
  opens) must see the same database. In-memory SQLite would give each
  connection its own empty database.
- `client` fixture (function scope): overrides `get_db` with
  `TestingSessionLocal`, runs `Base.metadata.create_all(bind=engine)`
  before the test and `drop_all` after, then clears
  `dependency_overrides`. Every test gets a fresh empty schema.
- `test_db` fixture: a separate session bound to the same engine, for
  seeding data directly via `create_*` + `commit()`.
- `SAMPLE_DEVICE_1/2/3` are module-level dicts — reuse them instead of
  inventing new sample data.
- Auth is off in tests: `api_token` defaults to empty, so `verify_token`
  skips validation. Do NOT add auth headers to test requests.

## Testing broadcast-trigger routes

For routes that call `comm.send` (see `api/broadcast-trigger-routes`):

```python
sent: list = []
monkeypatch.setattr(settings, "node_listener", "192.168.1.99")  # non-empty -> 202 path
monkeypatch.setattr(comm, "send", lambda payload: sent.append(payload))

resp = client.post(f"/api/devices/{device.id}/rescan/userspace")

assert resp.status_code == 202
assert sent == [{"event": "system.userspace.get_hash", "targets": [device.node]}]
```

- **Full-dict payload equality** — the *absence* of the `parameters` key is
  part of the assertion; do not assert payload keys individually.
- **Error branches assert `sent == []`** — 400/404/503 tests prove the guard
  order by showing nothing was broadcast.
- **503 branch** — `monkeypatch.setattr(settings, "node_listener", "")`
  (the default; `NODE_LISTENER` is empty in tests), so 202 cases must set a
  non-empty value explicitly.

Occurrences: `test_node_update_api.py` (`_trigger` helper),
`test_node_query_api.py`.
