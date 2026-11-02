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
