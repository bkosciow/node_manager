.PHONY: dev dev-build dev-down test test-unit test-integration lint clean help \
        build-prod prod-up prod-down prod-logs prod-build

# ===========================================
# Development
# ===========================================

dev: ## Start development environment
	docker compose up

dev-build: ## Rebuild and start development
	docker compose up --build

dev-down: ## Stop development environment
	docker compose down

dev-logs: ## Follow logs
	docker compose logs -f app

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
