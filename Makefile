# Delta Feed — Development & Maintenance Tasks
#
# Assumptions:
# - uv is installed (https://docs.astral.sh/uv/)
# - Node 22+ & npm installed (loaded automatically via nvm if available)

SHELL := /bin/bash

# Ensure nvm-managed Node 22 is used if system node is outdated (Astro / npm requirement)
NVM_INIT := if [ -s "$$HOME/.nvm/nvm.sh" ]; then . "$$HOME/.nvm/nvm.sh" && nvm use 22 >/dev/null 2>&1 || true; fi

BACKEND_DIR := backend
FRONTEND_DIR := frontend
SCRIPTS_DIR := scripts

DJANGO_DEBUG ?= true
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 4321
BACKEND_URL ?= http://localhost:$(BACKEND_PORT)

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help message
	@echo "Delta Feed Makefile targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Setup & Environment ---

.PHONY: init
init: ## Run bootstrap script for backend & frontend
	@$(NVM_INIT) && ./scripts/init.sh

.PHONY: install
install: install-backend install-frontend ## Install dependencies for both backend and frontend

.PHONY: install-backend
install-backend: ## Sync backend Python dependencies via uv
	cd $(BACKEND_DIR) && uv sync

.PHONY: install-frontend
install-frontend: ## Install frontend npm dependencies
	@$(NVM_INIT) && cd $(FRONTEND_DIR) && npm install

# --- Development Servers ---

.PHONY: dev-backend
dev-backend: ## Run Django development server (default port: 8000)
	cd $(BACKEND_DIR) && DJANGO_DEBUG=$(DJANGO_DEBUG) uv run python manage.py runserver $(BACKEND_PORT)

.PHONY: dev-frontend
dev-frontend: ## Run Astro frontend dev server (default port: 4321)
	@$(NVM_INIT) && cd $(FRONTEND_DIR) && BACKEND_URL=$(BACKEND_URL) npm run dev -- --port $(FRONTEND_PORT)

.PHONY: run-worker
run-worker: ## Run backend background job worker
	cd $(BACKEND_DIR) && DJANGO_DEBUG=$(DJANGO_DEBUG) uv run python manage.py run_worker

# --- Testing & Quality Assurance ---

.PHONY: test
test: test-backend test-frontend ## Run test suites for both backend and frontend

.PHONY: test-backend
test-backend: ## Run backend pytest suite
	cd $(BACKEND_DIR) && uv run pytest -q

.PHONY: test-frontend
test-frontend: ## Run frontend vitest suite
	@$(NVM_INIT) && cd $(FRONTEND_DIR) && npm test

.PHONY: check
check: lint typecheck test ## Run full quality checks: lint, typecheck, tests

.PHONY: lint
lint: lint-backend ## Run linters (ruff for backend)

.PHONY: lint-backend
lint-backend: ## Run ruff linter on backend
	cd $(BACKEND_DIR) && uv run ruff check .

.PHONY: format
format: ## Auto-format backend code with ruff
	cd $(BACKEND_DIR) && uv run ruff format . && uv run ruff check --fix .

.PHONY: typecheck
typecheck: typecheck-frontend ## Run type checks (tsc for frontend)

.PHONY: typecheck-frontend
typecheck-frontend: ## Run TypeScript compiler check on frontend
	@$(NVM_INIT) && cd $(FRONTEND_DIR) && npx tsc --noEmit

# --- Build ---

.PHONY: build
build: build-frontend ## Build frontend application

.PHONY: build-frontend
build-frontend: ## Build frontend SSR bundle with Astro
	@$(NVM_INIT) && cd $(FRONTEND_DIR) && npm run build

# --- Database & Django Ops ---

.PHONY: migrate
migrate: ## Apply database migrations
	cd $(BACKEND_DIR) && DJANGO_DEBUG=$(DJANGO_DEBUG) uv run python manage.py migrate

.PHONY: makemigrations
makemigrations: ## Generate database migrations
	cd $(BACKEND_DIR) && DJANGO_DEBUG=$(DJANGO_DEBUG) uv run python manage.py makemigrations

.PHONY: setup-token
setup-token: ## Print setup token for first-time reader setup
	cd $(BACKEND_DIR) && DJANGO_DEBUG=$(DJANGO_DEBUG) uv run python manage.py setup_token

.PHONY: superuser
superuser: ## Create a Django superuser
	cd $(BACKEND_DIR) && DJANGO_DEBUG=$(DJANGO_DEBUG) uv run python manage.py createsuperuser

.PHONY: clean
clean: ## Remove temporary caches, build artifacts and python bytecode
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/.ruff_cache
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/.astro
