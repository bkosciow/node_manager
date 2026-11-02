# Standalone DB Bootstrap (CLI scripts)

- Standalone scripts (repo_scanner.py & similar) build their own engine in
  `main()`:
  `create_engine(settings.database_url)` +
  `Base.metadata.create_all(bind=engine)` + local
  `sessionmaker(autocommit=False, autoflush=False, bind=engine)`.
- Never reuse `app.db.session.SessionLocal` — it binds the FastAPI app's
  engine; scripts run as separate processes/containers.
- `create_all` at startup is deliberate: schema = models, no migration
  tooling (GUARDRAILS architectural decision "Schema = models, no
  migration tool").
- One session for the whole script run; `db.close()` in `finally`;
  top-level exception → `logger.exception` + `sys.exit(1)`.
