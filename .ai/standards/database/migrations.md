# Migrations (Alembic)

- Schema is versioned by Alembic. Revisions live under `migrations/versions/`
  as sequential 4-digit ids (`0001_baseline.py`, then `0002_...`);
  `alembic.ini` points `script_location` at `migrations/` and ships an
  **empty** `sqlalchemy.url`.
- The DB URL always comes from `settings.database_url` (single source of
  truth, GUARDRAILS / `global/config-settings`). `migrations/env.py` falls
  back to `settings.database_url` when the ini URL is empty;
  `app/db/migrate.py` sets it explicitly.
- `run_migrations()` (`app/db/migrate.py`) runs `alembic upgrade head`
  in-process, anchored to the repo root via
  `Path(__file__).resolve().parents[2]` so it is CWD-independent.
- Every entrypoint calls `run_migrations()` at startup, before touching the
  DB: `rest_server.startup()`, `device_scaner.main()`,
  `repo_scanner.main()`, and `scripts/backfill_node_update_files.py`.
- `create_all` is gone from the app path — do not reintroduce it. The schema
  source of truth is the revision history, not `Base.metadata.create_all`.
- New schema change: edit the model → `make autogenerate MSG=<slug>` →
  review the generated revision (rename to the next 4-digit id, set
  `revision` + `down_revision`) → `make migrate` to apply on dev. Never
  hand-edit an applied revision.
- The baseline `0001` has `down_revision = None` and its DDL is dialect-safe
  (SQLite-compatible), which is why the in-process run and the tests below
  work without a skip marker.
- Tests stay migration-independent: `tests/conftest.py` no-ops
  `app.rest_server.run_migrations` (autouse fixture); the test engine's own
  `Base.metadata.create_all` on a file-based SQLite DB is the schema source
  for the suite, never a revision run.
