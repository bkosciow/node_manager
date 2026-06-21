.PHONY: dev dev-build dev-down test test-unit test-integration lint clean help \
        build-prod prod-up prod-down prod-logs prod-build

# ===========================================
# Development
# ===========================================

dev: ## Start development server (venv)
	source .venv/bin/activate && python -m uvicorn app.rest_server:app --reload

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
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $1, $2}'

.DEFAULT_GOAL := help
