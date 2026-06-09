# Constraints

## Deployment
- Target: Local machine (dev) using Python venv (`.venv`). Production TBD — LAN-based.
- Region: N/A (internal network)
- Scanner: Separate Docker container with `/upgrades` volume mapping, runs periodically.

## Scale
- Launch: 1 user, high-frequency UDP message stream ("flood"), ~tens to hundreds of unique devices; ~10 repos
- 6 months: Unknown growth; no hard caps

## Budget
- Infrastructure: Self-hosted, minimal to no cost
- Tooling: Free / open-source only

## Compliance & Security
- Personal data only — no regulatory requirements
- No authentication for MVP (internal network)

## Tech Stack Preferences
- Language: Python
- Framework: FastAPI
- Database: MySQL (via `mysql+mysqlconnector`)
- ORM: SQLAlchemy with `Mapped[]` + `mapped_column()` pattern
- Message transport: UDP broadcast via `message_listener` package
- Config: `pydantic_settings.BaseSettings` via `app/config.py`
- Additional: `iot_message` package for message serialization
- Scanner: Standalone Python script, same DB/config as API, SHA256 from stdlib (`hashlib`)
