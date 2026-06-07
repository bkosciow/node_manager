# Constitution

## Non-Negotiables
- **No duplicates in DB** — enforced by unique constraint on `(chip_id, node)` in the devices table. The in-memory cache is a performance optimization; the DB constraint is the final guard.

## Explicit Non-Goals
- **Not a real-time monitoring dashboard** — this service discovers and stores devices. Monitoring/visualization is handled by the frontend.
- **Not multi-tenant** — single operator, single deployment. No isolation between users or tenants.

## Technical Constraints
- Must integrate with existing Python stack: **FastAPI + SQLAlchemy + MySQL** (`mysql+mysqlconnector`).
- DB connection via `.env` (`DATABASE_URL`), config via `app/config.py` (`pydantic_settings`).
- Message ingestion uses existing UDP broadcast listener (`message_listener` package) on `NODE_LISTENER:NODE_LISTENER_PORT`.
- Handler lives at `app/message_handler/device_discovery.py`, implementing `Handler.handle(message)`.
- Message structure: `message.data` is a dict with `chip_id` (unique device ID) and `node` (device name, not unique).
- Models and CRUD directories are empty — awaiting implementation.
- Follow existing coding standards (coding_standards.md): `Mapped[]` columns, `snake_case`, type hints, `verify_token` auth pattern, Pydantic schemas with Base/Create/Update/Response.

## Timeline & Resources
- **Timeline**: No hard deadline. Build at own pace.
- **Team**: Solo developer.
- **Constraints**: None.
