.PHONY: dev dev-build dev-down test test-unit test-integration lint clean help \
        build-prod prod-up prod-down prod-logs prod-build \
        migrate autogenerate reset-dev-db

# ===========================================
# Development
# ===========================================

dev: ## Start development server (venv)
	source .venv/bin/activate && uvicorn app.rest_server:app --reload --host 0.0.0.0 --port 9092

dev-scanner: ## Run UDP device scanner
	source .venv/bin/activate && python device_scaner.py

dev-repo-scanner: ## Run repository file scanner
	source .venv/bin/activate && python repo_scanner.py

# ===========================================
# Testing
# ===========================================

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests
	pytest tests/unit/ -v

test-integration: ## Run integration tests
	pytest tests/integration/ -v

test-coverage: ## Run tests with coverage
	pytest tests/ -v --cov=app --cov-report=term-missing

# ===========================================
# Code Quality
# ===========================================

lint: ## Run linter
	flake8 app/ tests/ --count --show-source --statistics

# ===========================================
# Database
# ===========================================

db-shell: ## Connect to MySQL shell
	docker compose exec db mysql -unode_manager -ppostgres node_manager_dev

migrate: ## Apply pending migrations (alembic upgrade head)
	.venv/bin/alembic upgrade head

autogenerate: ## Generate a revision (usage: make autogenerate MSG=<slug>)
	$(if $(MSG),,$(error MSG is required -- usage: make autogenerate MSG=<slug>))
	.venv/bin/alembic revision --autogenerate -m "$(MSG)"

# Read DATABASE_URL from the repo .env (Make does not load .env itself);
# used only for the dev-only guard below.
DATABASE_URL := $(shell sed -n 's/^DATABASE_URL=//p' .env 2>/dev/null)

reset-dev-db: ## Dev-only: drop/create node_manager_dev + apply migrations
	$(if $(DATABASE_URL),,$(error .env DATABASE_URL not found -- create .env (see .env.example) first))
	@case "$(DATABASE_URL)" in *node_manager_dev*) : ;; *) echo "error: reset-dev-db is dev-only: DATABASE_URL must target node_manager_dev"; exit 1 ;; esac
	@if ! ls migrations/versions/*.py >/dev/null 2>&1; then \
	echo 'error: no revisions in migrations/versions/ -- generate the baseline first:'; \
	echo '  1) docker compose exec db mysql -uroot -ppostgres -e "DROP DATABASE IF EXISTS node_manager_dev; CREATE DATABASE node_manager_dev"'; \
	echo '  2) .venv/bin/alembic revision --autogenerate -m baseline'; \
	echo '     then rename to 0001_baseline.py (revision = "0001", down_revision = None), commit, and re-run'; \
	exit 1; fi
	@echo '==> dropping and creating node_manager_dev'
	docker compose exec db mysql -uroot -ppostgres -e "DROP DATABASE IF EXISTS node_manager_dev; CREATE DATABASE node_manager_dev"
	@echo '==> applying migrations (alembic upgrade head)'
	.venv/bin/alembic upgrade head
	@echo 'done -- re-assign repos to nodes, then run: make dev-repo-scanner'

# ===========================================
# Production
# ===========================================

prod-build: ## Build production Docker image
	docker compose -f docker-compose.prod.yml build

prod-up: ## Start production environment
	docker compose -f docker-compose.prod.yml up -d

prod-down: ## Stop production environment
	docker compose -f docker-compose.prod.yml down

prod-logs: ## View production logs
	docker compose -f docker-compose.prod.yml logs -f

prod-restart: ## Restart production services
	docker compose -f docker-compose.prod.yml restart

# ===========================================
# Cleanup
# ===========================================

clean: ## Clean build artifacts and containers
	docker compose down -v
	docker compose -f docker-compose.prod.yml down -v 2>/dev/null || true
	rm -rf __pycache__ .pytest_cache .coverage htmlcov *.egg-info

# ===========================================
# Help
# ===========================================

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
