# Tech Stack

## Core

| Layer | Technology | Version | Rationale |
|-------|------------|---------|-----------|
| Language | Python | 3.13 | Existing codebase, `message_listener` and `iot_message` packages are Python |
| Web Framework | FastAPI | latest | Already in use (`rest_server.py`). Async, auto OpenAPI docs, Pydantic integration |
| Database | MySQL | 8.0 | Existing infrastructure, production-ready |
| DB Driver | mysql-connector-python | — | Existing (`mysql+mysqlconnector` in DATABASE_URL) |
| ORM | SQLAlchemy | 2.x | Already in use. `Mapped[]` + `mapped_column()` pattern per coding standards |
| Config | pydantic-settings | latest | `BaseSettings` with `.env` support, already in `app/config.py` |
| HTTP Client | requests | — | Used by service integrations (Apprise, Jellyfin, Transmission) |

## Message Processing

| Layer | Technology | Rationale |
|-------|------------|-----------|
| UDP Listener | `message_listener` | Existing package. Handles UDP broadcast reception and handler registration |
| Message Format | `iot_message` | Existing package. Provides message serialization/parsing |
| Internal Queue | `queue.Queue` | stdlib, thread-safe, unbounded — no external dependency |
| Threading | `threading` | stdlib. Worker daemon thread for async processing |

## API

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Server | uvicorn | FastAPI default ASGI server |
| Auth | `app.auth.verify_token` | Existing token-based auth (graceful skip when `API_TOKEN` is empty) |
| API Docs | Swagger UI (`/docs`) | FastAPI auto-generates from type hints + decorators |
| Schema Validation | Pydantic v2 | FastAPI built-in, `field_validator` for custom logic |

## Testing

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Unit tests | pytest | Python standard, mocks for queue/DB/cache |
| Integration tests | pytest + FastAPI TestClient | SQLite for fast in-memory DB testing, real HTTP client |
| Coverage | pytest-cov | Optional, 80%+ target |

## Development

| Tool | Purpose |
|------|---------|
| flake8 | Linting (configured via `.flake8`, 100 char limit) |
| mypy | Static type checking |
| Python venv | Local dev environment (`.venv`) |

## Deployment

| Layer | Technology | Status |
|-------|------------|--------|
| Dev | Python venv | Current |
| Production | Docker + docker compose | Scaffolded |
| CI/CD | GitHub Actions | Lint + test + Docker build |
| Container | Docker | Multi-stage build, non-root user, health check |

## Hash Scanning

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Script | Standalone Python | Same DB/config as API, independent entrypoint |
| Hash | `hashlib.sha256` | stdlib, no external dependency |
| Schedule | Docker container (periodic) | `/upgrades` volume mapping, runs independently |

## Notifications (Optional)

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Apprise | apprise library | Multi-protocol notification service, optional via config |

## Media Services (Optional)

| Service | Integration | Purpose |
|---------|-------------|---------|
| Jellyfin | REST API via `requests` | Media library management |
| Transmission | RPC API via `requests` | Torrent client management |

## Versions

```json
{
  "python": "3.13",
  "fastapi": ">=0.115.0",
  "uvicorn": ">=0.30.0",
  "pydantic": ">=2.0.0",
  "pydantic-settings": ">=2.0.0",
  "sqlalchemy": ">=2.0.0",
  "mysql-connector-python": "latest",
  "pytest": "latest",
  "flake8": "latest",
  "mysql": "8.0"
}
```
