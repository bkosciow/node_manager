# Deployment Guide

## Docker Compose (Production)

### Prerequisites

- Server with Docker & Docker Compose installed
- MySQL accessible (either via Docker or external)

### Step 1: Clone and Configure

```bash
git clone <repo-url>
cd node_manager
cp .env.example .env
```

Edit `.env` with production values:

```bash
DATABASE_URL=mysql+mysqlconnector://node_manager:STRONG_PASSWORD@db:3306/node_manager
API_TOKEN=GENERATE_A_SECURE_TOKEN
NODE_NAME=node_manager
NODE_ID=node_manager_1
```

Generate a secure API token:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 2: Deploy

```bash
# Build and start
make prod-up

# Or with docker compose directly:
docker compose -f docker-compose.prod.yml up -d --build

# Check status
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

### Step 3: Verify

```bash
# Health check
curl http://localhost:9092/health

# API docs
open http://localhost:9092/docs
```

## Maintenance

```bash
# View logs
make prod-logs

# Restart
make prod-restart

# Update and redeploy
git pull
make prod-build
make prod-up

# Stop
make prod-down

# Backup database
docker compose -f docker-compose.prod.yml exec db \
  mysqldump -unode_manager -pSTRONG_PASSWORD node_manager > backup.sql
```

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make dev` | Start development environment |
| `make dev-down` | Stop development |
| `make prod-build` | Build production image |
| `make prod-up` | Start production |
| `make prod-down` | Stop production |
| `make prod-logs` | View production logs |
| `make test` | Run all tests |
| `make lint` | Run linter |
| `make clean` | Remove containers and volumes |
