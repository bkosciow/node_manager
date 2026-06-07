# Constitution — Event Data Extension

## Non-Negotiables
- Upsert semantics: always store the latest value, overwrite silently.
- Events are tied to a Device via `(chip_id, node)` — if the device doesn't exist yet, create it first.
- Parameters stored as JSON — structure is unknown and may vary per device/firmware.

## Explicit Non-Goals
- Historical tracking — only the latest value is kept.
- Event validation — we don't validate the shape of the parameters JSON.
- Real-time push — polling via REST API only.
- Supporting event types beyond the 3 defined ones (extensible, but not in scope).

## Technical Constraints
- Must integrate with existing `MessageHandler` in `app/message_handler/device_discovery.py`.
- Must use existing SQLAlchemy models, CRUD, and FastAPI patterns from the codebase.
- Database: SQLite (dev) / whatever is configured via `database_url`.
- No new external dependencies.

## Timeline & Resources
- Timeline: no hard deadline.
- Team: solo developer.
- Constraints: none.
