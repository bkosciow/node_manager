# Unit Test Idiom (tests/unit/)

- Module-level in-memory engine:
  `create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})`
  + `TestingSession` sessionmaker.
- `autouse` fixture: `Base.metadata.create_all` before, `drop_all` after
  each test.
- Sessions: current convention is the `db_session` pytest fixture
  (yield + close in `try/finally`), used by all `*_crud.py` test files.
  The older `next(_session())` generator idiom remains in the earliest
  files (`test_device_crud.py`, `test_event_crud.py`,
  `test_device_event_model.py`) — legacy, don't extend it. Prefer
  `db_session` for new test files.
- Import the model under test at module top:
  `from app.models.device import Device  # noqa: F401 — register model
  with Base` — without it, `create_all` doesn't know the table.
- In-memory works ONLY when the code under test uses sessions from your
  engine. Code that opens its own connection (e.g.
  `MessageHandler._process` via `session_factory()`) needs a file-based
  SQLite — in-memory gives each new connection its own empty database.
- One test class per CRUD function (`TestCreateDevice`, `TestGetDevice`,
  …) with `# -- function ---` section comments; cover missing → None,
  skip/limit, and `pytest.raises(IntegrityError)` for unique constraints.
