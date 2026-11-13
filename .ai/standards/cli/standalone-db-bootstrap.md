# Standalone DB Bootstrap (CLI scripts)

- Standalone scripts (repo_scanner.py & similar) build their own engine in
  `main()`: `create_engine(settings.database_url)` +
  `run_migrations()` + local
  `sessionmaker(autocommit=False, autoflush=False, bind=engine)`.
- Never reuse `app.db.session.SessionLocal` — it binds the FastAPI app's
  engine; scripts run as separate processes/containers.
- Schema bootstrap is `run_migrations()` (Alembic, SPEC-005), not
  `create_all` — `create_all` is retired from app code paths. See
  `database/migrations`.
- One session for the whole script run; `db.close()` in `finally`;
  top-level exception → `logger.exception` + `sys.exit(1)`.
