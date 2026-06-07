# Tech Stack — Event Data Extension

## Inherited from Existing Project

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language | Python | 3.x | Existing codebase |
| Web Framework | FastAPI | latest | Existing (`rest_server.py`) |
| Database | MySQL | — | Existing infrastructure |
| DB Driver | mysql-connector-python | — | Existing |
| ORM | SQLAlchemy 2.x | 2.x | Existing, `Mapped[]` pattern |
| Config | pydantic-settings | latest | Existing |

## Extension-Specific Additions

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| JSON column | SQLAlchemy `JSON` type | Native MySQL JSON, mapped via SQLAlchemy. Supports `dict` round-trip |
| Upsert | `insert().on_duplicate_key_update()` | MySQL-specific upsert via SQLAlchemy, one query |
| Event types | `Literal` type hint | Type-safe event type validation at Python level |

## No New Dependencies
The extension uses only stdlib and existing project dependencies. No `pip install` required.
