# IoT Device Discovery Service

Discovers and deduplicates IoT devices from UDP broadcast messages. Runs a background worker to parse incoming messages, deduplicate via an in-memory cache, and persist unique devices to MySQL. Exposes a FastAPI REST API for browsing discovered devices.

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

# Start development environment (app + MySQL)
make dev

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
python -m uvicorn app.rest_server:app --host 0.0.0.0 --port 9092 --reload

# Start UDP scanner in a separate terminal
python device_scaner.py
```

### Running Tests

```bash
make test           # All tests
make test-unit      # Unit tests only
make test-integration  # Integration tests only
make lint           # Run flake8
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | MySQL connection string |
| `APP_HOST` | No | `0.0.0.0` | REST API bind address |
| `APP_PORT` | No | `9092` | REST API port |
| `API_TOKEN` | No | `` | Bearer token for API auth (empty = skip) |
| `NODE_NAME` | No | `node_manager` | This node's name |
| `NODE_ID` | No | `node_manager_1` | This node's chip ID |
| `NODE_LISTENER_PORT` | No | `5053` | UDP listener port |
| `APPRISE_URL` | No | `` | Apprise notification URL (empty = disabled) |
| `SL_PASSPHRASE` | No | `` | Message encryption passphrase (empty = no encryption) |

See `.env.example` for all options.

## Architecture

- **UDP Listener** (`device_scaner.py`) — receives broadcast messages via `message_listener`
- **Message Handler** (`app/message_handler/`) — parses messages, extracts `(chip_id, node)`, pushes to thread-safe queue
- **Discovery Worker** — background daemon thread drains queue, deduplicates via in-memory cache, persists to MySQL
- **REST API** (`app/rest_server.py`) — FastAPI server with paginated device listing
- **Database** — MySQL with SQLAlchemy ORM, composite unique constraint on `(chip_id, node)`

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | List all devices (paginated) |
| GET | `/api/devices/{id}` | Get single device by ID |
| GET | `/health` | Health check |

Full OpenAPI spec: [`.prodready/design/api/openapi.yaml`](.prodready/design/api/openapi.yaml)

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for production deployment guide.

## Project Structure

```
app/
├── rest_server.py          # FastAPI app + routes
├── auth.py                 # Token authentication
├── config.py               # Pydantic settings
├── models/device.py        # SQLAlchemy Device model
├── schemas/device.py       # Pydantic schemas
├── crud/device.py          # CRUD operations
├── db/                     # Database setup
├── message_handler/        # Message parsing + worker
└── services/               # External service integrations
tests/
├── unit/                   # Unit tests
└── integration/            # Integration tests
device_scaner.py            # UDP scanner entry point
```
