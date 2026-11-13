# Node Manager

Discovers and deduplicates IoT devices from UDP broadcast messages. Runs a UDP listener to parse incoming messages, deduplicates via an in-memory cache, and persists unique devices and their special event payloads (`system.pong`, `system.microplate.hash`, `system.userspace.hash`) to MySQL.

It also manages versioned file repositories (via `repo_scanner.py` and a periodic auto-scan) and orchestrates device upgrades: broadcasts upgrade commands over UDP, serves the updated files, and validates the hashes nodes report back. Everything is exposed through a FastAPI REST API.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.13 + venv (for local development without Docker)

### Development (Docker)

```bash
# Clone and enter project
git clone <repo-url>
cd node_manager

# Copy environment file and edit as needed
cp .env.example .env

# Start development environment (API + UDP scanner + MySQL)
docker compose up

# API available at http://localhost:9092
# API docs at http://localhost:9092/docs
```

### Development (venv)

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start REST API (MySQL must be running separately)
make dev

# Start UDP scanner in a separate terminal
make dev-scanner

# Optionally: sync repository file hashes to the DB
make dev-repo-scanner
```

### Running Tests

```bash
make test                  # All tests
make test-unit             # Unit tests only
make test-integration      # Integration tests only
make test-coverage         # Tests with coverage report
make lint                  # Run flake8
```

## Database Migrations

The schema is versioned with [Alembic](https://alembic.sqlalchemy.org/).
Revisions live under `migrations/versions/` (`0001` baseline + later
revisions). `app/db/migrate.py` runs `alembic upgrade head` in-process, so
the API, scanner, and repo scanner apply any pending migration at startup —
in the normal flow there is nothing to run by hand.

Manual / development commands (see `Makefile`):

| Action | Command |
|--------|---------|
| Apply pending migrations | `make migrate` |
| Generate a revision from model changes | `make autogenerate MSG=<slug>` |
| Reset the dev DB (drop/create + migrate) | `make reset-dev-db` |

`reset-dev-db` is dev-only — it refuses to run against a non-dev
`DATABASE_URL`. Production schema changes ship as new revision files and are
applied automatically on container start.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | MySQL connection string |
| `APP_HOST` | No | `0.0.0.0` | REST API bind address |
| `APP_PORT` | No | `8577` | REST API port (dev environments use `9092`) |
| `API_TOKEN` | No | `` | Bearer token for API auth (empty = auth disabled) |
| `UPGRADES_DIR` | No | `./upgrades` | Directory holding repository files served during upgrades |
| `REPO_SCAN_INTERVAL_MINUTES` | No | `10` | Auto-rescan repositories every N minutes (0 disables the auto-scanner) |
| `BASE_URL` | No | `` | Public base URL included in upgrade broadcasts (empty = `http://APP_HOST:APP_PORT`) |
| `APPRISE_URL` | No | `` | Apprise notification URL (empty = disabled) |
| `APPRISE_TAG` | No | `` | Apprise tag filter for notifications |
| `PUID` / `GUID` | No | `1000` | Run user/group ID (container user) |
| `NODE_NAME` | No | `` | This node's name (Docker default: `node_manager`) |
| `NODE_ID` | No | `` | This node's chip ID (Docker default: `node_manager_1`) |
| `NODE_LISTENER` | No | `` | UDP target address for bootstrap and upgrade broadcasts (empty = no broadcast target) |
| `NODE_LISTENER_PORT` | No | `5053` | UDP listener port |
| `SL_STATISIV` / `SL_IVKEY` / `SL_DATAKEY` / `SL_PASSPHRASE` | No | `` | Message encryption keys (empty = no encryption) |

See `.env.example` for all options.

## Architecture

- **UDP Listener** (`device_scaner.py`) — receives broadcast messages via `message_listener`, persists discovered devices and event payloads
- **Message Handler** (`app/message_handler/`) — parses messages, extracts `(chip_id, node)`, detects special events, pushes tagged items to a thread-safe queue
- **Discovery Worker** — background daemon thread drains the queue, deduplicates devices via in-memory cache, upserts event data, persists to MySQL
- **Repository Scanner** (`repo_scanner.py`) — standalone CLI that hashes files under `UPGRADES_DIR` and upserts `Repository`/`RepositoryFile` rows
- **Auto-scanner** (`app/services/repo_scan.py`) — background thread started with the API; re-scans all repositories every `REPO_SCAN_INTERVAL_MINUTES` and syncs DB records
- **Upgrade flow** (`app/services/comm.py`, `app/services/iot_bootstrap.py`) — broadcasts `system.files.upgrade` UDP messages with a UUID-scoped download URL; the API serves files and validates reported hashes
- **REST API** (`app/rest_server.py`) — FastAPI server: devices, events, repositories, assignments, and upgrade sessions
- **Database** — MySQL with SQLAlchemy ORM, composite unique constraints on `(chip_id, node)` and `(device_id, event_type)`

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/devices` | List devices (paginated, includes `updates_available` flag) |
| GET | `/api/devices/{id}` | Device details: logged events + assigned repos with updatable files |
| GET | `/api/devices/{id}/events` | All event data for a device, keyed by event type |
| GET | `/api/devices/{id}/events/{event_type}` | Latest parameters for one event type |
| GET | `/api/devices/{id}/ignored-files` | List ignored files for a device |
| POST | `/api/devices/{id}/ignored-files` | Add an ignored file |
| DELETE | `/api/devices/{id}/ignored-files` | Remove an ignored file (`repo_type` + `filename` query params) |
| GET | `/api/devices/{id}/updates` | List upgrade sessions for a device (newest first) |
| POST | `/api/devices/{id}/update/{repo_type}` | Broadcast an upgrade for the repo-side diff (202) |
| POST | `/api/devices/{id}/ping` | Broadcast a liveness ping to the device (202) |
| POST | `/api/devices/{id}/rescan/{repo_type}` | Ask the device to re-report its file hashes for the repo type (202) |
| GET | `/api/repos?type={repo_type}` | List repositories of a type with their files and hashes |
| POST | `/api/repos/{id}/rescan` | Re-hash this repo's on-disk files and sync the DB records |
| POST | `/api/nodes/{device_id}/repos` | Assign a repository to a node |
| GET | `/api/update/{token}/get/{filename}` | *(public, UUID-scoped)* Download an upgrade file |
| POST | `/api/update/{token}/validate/{filename}` | *(public, UUID-scoped)* Validate a downloaded file hash |

Interactive docs: `http://localhost:9092/docs` (OpenAPI at `/openapi.json`).

## Deployment

Production uses `docker-compose.prod.yml`:

```bash
make prod-build   # Build production image
make prod-up      # Start production environment
make prod-down    # Stop
make prod-logs    # Tail logs
```

## Project Structure

```
app/
├── rest_server.py               # FastAPI app + all REST endpoints
├── auth.py                      # Bearer token authentication
├── config.py                    # Pydantic settings
├── models/                      # SQLAlchemy models
│   ├── device.py                # Device (discovered IoT node)
│   ├── device_event.py          # DeviceEvent (event payloads)
│   ├── device_ignored_file.py   # Per-device ignored files
│   ├── repository.py            # Repository + RepositoryFile
│   ├── node_repository.py       # NodeRepository (device↔repo assignments)
│   ├── node_update.py           # NodeUpdate (upgrade sessions)
│   └── node_update_file.py      # Per-file progress within an upgrade
├── schemas/                     # Pydantic schemas (one file per resource)
├── crud/                        # Database operations (one file per resource)
├── db/                          # Database setup (base, session, relationships)
├── message_handler/             # Message parsing + discovery worker
└── services/                    # apprise.py, comm.py (UDP), iot_bootstrap.py, repo_scan.py
tests/
├── unit/                        # Unit tests
└── integration/                 # Integration tests (API endpoints)
device_scaner.py                 # UDP scanner entry point
repo_scanner.py                  # Repository file scanner CLI
```
