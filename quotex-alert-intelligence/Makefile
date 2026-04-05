.PHONY: install-backend install-extension run-backend run-dev build-extension test-backend init-db seed-settings docker-up docker-down clean

# Backend
install-backend:
	cd backend && pip install -r requirements.txt

install-extension:
	cd extension && npm install

run-backend:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-dev:
	bash scripts/dev_run.sh

# Extension
build-extension:
	cd extension && npm run build

# Testing
test-backend:
	cd backend && pytest -v

# Database
init-db:
	python scripts/init_indexes.py

seed-settings:
	python scripts/seed_settings.py

# Docker
docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf backend/.pytest_cache
	rm -rf backend/htmlcov
	rm -rf backend/.coverage
	rm -rf extension/dist
	rm -rf extension/build
	rm -rf extension/node_modules
	rm -rf backend/.venv
