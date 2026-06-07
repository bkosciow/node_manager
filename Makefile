.PHONY: dev dev-build dev-down test test-unit test-integration lint clean help

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
# Cleanup
# ===========================================

clean: ## Clean build artifacts and containers
	docker compose down -v
	rm -rf __pycache__ .pytest_cache .coverage htmlcov *.egg-info

# ===========================================
# Help
# ===========================================

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $1, $2}'

.DEFAULT_GOAL := help
