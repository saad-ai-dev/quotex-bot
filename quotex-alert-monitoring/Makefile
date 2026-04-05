# Quotex Alert Monitor - Makefile
# ALERT-ONLY: Build and run targets for the monitoring system.

.PHONY: help install-backend install-dashboard install-extension \
        run-backend build-dashboard build-extension \
        test docker-up docker-down clean dev

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---- Installation ----

install-backend: ## Install backend Python dependencies
	cd backend && pip install -r requirements.txt

install-dashboard: ## Install dashboard Node dependencies
	cd dashboard && npm install

install-extension: ## Install extension Node dependencies
	cd extension && npm install

install: install-backend install-dashboard install-extension ## Install all dependencies

# ---- Development ----

run-backend: ## Start the backend server (uvicorn)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-dashboard: ## Start the dashboard dev server
	cd dashboard && npm run dev

dev-extension: ## Build extension in watch mode
	cd extension && npm run dev

dev: ## Start all services for development (requires tmux or multiple terminals)
	@echo "Run these in separate terminals:"
	@echo "  make run-backend"
	@echo "  make run-dashboard"
	@echo "  make dev-extension"
	@echo ""
	@echo "Or use: ./scripts/dev_run.sh"

# ---- Build ----

build-dashboard: ## Build dashboard for production
	cd dashboard && npm run build

build-extension: ## Build extension for production
	cd extension && npm run build

build: build-dashboard build-extension ## Build all frontend assets

# ---- Testing ----

test: ## Run all tests
	cd backend && python -m pytest tests/ -v
	cd extension && npm run type-check

test-backend: ## Run backend tests only
	cd backend && python -m pytest tests/ -v

test-extension: ## Type-check extension only
	cd extension && npm run type-check

# ---- Docker ----

docker-up: ## Start Docker services (MongoDB + backend)
	docker-compose up -d

docker-down: ## Stop Docker services
	docker-compose down

docker-logs: ## Show Docker logs
	docker-compose logs -f

# ---- Database ----

init-db: ## Initialize MongoDB indexes
	python scripts/init_indexes.py

seed-db: ## Seed default settings
	python scripts/seed_settings.py

setup-db: init-db seed-db ## Initialize and seed database

# ---- Cleanup ----

clean: ## Clean build artifacts and caches
	rm -rf extension/dist
	rm -rf dashboard/dist dashboard/.next
	rm -rf backend/__pycache__ backend/**/__pycache__
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
