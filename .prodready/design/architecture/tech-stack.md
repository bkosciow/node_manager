# Tech Stack

## Core

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language | Python | 3.x | Existing codebase, `message_listener` and `iot_message` packages are Python |
| Web Framework | FastAPI | latest | Already in use (`rest_server.py`). Async, auto OpenAPI docs, Pydantic integration |
| Database | MySQL | — | Existing infrastructure, production-ready |
| DB Driver | mysql-connector-python | — | Existing (`mysql+mysqlconnector` in DATABASE_URL) |
| ORM | SQLAlchemy 2.x | 2.x | Already in use. `Mapped[]` + `mapped_column()` pattern per coding standards |
| Config | pydantic-settings | latest | `BaseSettings` with `.env` support, already in `app/config.py` |

## Message Processing

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| UDP Listener | `message_listener` | Existing package. Handles UDP broadcast reception and handler registration |
| Message Format | `iot_message` | Existing package. Provides message serialization/parsing |
| Internal Queue | `queue.Queue` | stdlib, thread-safe, unbounded — no external dependency |
| Threading | `threading` | stdlib. Worker daemon thread for async processing |

## API

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Server | uvicorn | FastAPI default ASGI server |
| Auth | `app.auth.verify_token` | Existing token-based auth (graceful skip when `API_TOKEN` is empty) |
| API Docs | Swagger UI (`/docs`) | FastAPI auto-generates from type hints + decorators |

## Testing

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Unit tests | pytest | Python standard, mocks for queue/DB/cache |
| Integration tests | pytest + SQLite | SQLite for fast in-memory DB testing, real FastAPI test client |
| Test client | `httpx` (via `TestClient`) | FastAPI test client for HTTP endpoint testing |

## Development

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Env | Python venv (`.venv`) | Per constraints — local dev with venv |
| Linter | flake8 | Already configured via `.flake8` |
| Type checking | mypy | Python static type checking |

## Deployment

| Layer | Technology | Status |
|-------|-----------|--------|
| Dev | Python venv | Current |
| Production | TBD | Not defined yet |
| Containerization | Docker | Phase 3.5 (Scaffold) |
