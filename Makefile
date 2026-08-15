# =============================================================================
# Cross-platform Makefile (Linux/macOS & Windows)
# =============================================================================

.DEFAULT_GOAL:=help
MAKEFLAGS += --no-print-directory

# Detect operating system
ifeq ($(OS),Windows_NT)
    IS_WINDOWS := 1
    NULL := NUL
    RM := del /q
    RMDIR := rd /s /q
    MKDIR := mkdir
    PYTHON := python
    FIND_DEL := for /d /r . %%d in
else
    IS_WINDOWS := 0
    NULL := /dev/null
    RM := rm -rf
    RMDIR := rm -rf
    MKDIR := mkdir -p
    PYTHON := python3
    FIND_DEL := find . -name
endif

# Status labels. Unix color codes are split to avoid shell metacharacters
# when expanded unquoted in recipes.
ifeq ($(IS_WINDOWS),1)
    INFO := [INFO]
    OK := [OK]
    WARN := [WARN]
    ERROR := [ERROR]
else
    BOLD := $(shell printf "\033[1m")
    BLUE := $(shell printf "\033[34m")
    GREEN := $(shell printf "\033[32m")
    RED := $(shell printf "\033[31m")
    YELLOW := $(shell printf "\033[33m")
    NC := $(shell printf "\033[0m")
    INFO := $(BOLD)$(BLUE)[INFO]$(NC)
    OK := $(BOLD)$(GREEN)[OK]$(NC)
    WARN := $(BOLD)$(YELLOW)[WARN]$(NC)
    ERROR := $(BOLD)$(RED)[ERROR]$(NC)
endif

# Shell configuration
ifeq ($(IS_WINDOWS),1)
    SHELL := cmd
    .SHELLFLAGS := /c
else
    SHELL := /bin/bash
    .ONESHELL:
    .EXPORT_ALL_VARIABLES:
endif

# =============================================================================
# Help
# =============================================================================

.PHONY: help
help:				## Display this help text for Makefile
ifeq ($(IS_WINDOWS),1)
	@echo.
	@echo Usage:
	@echo   make ^<target^>
	@echo.
	@echo Available targets:
	@echo   sync              Sync dependencies
	@echo   install           Install dependencies
	@echo   lock              Rebuild lockfiles from scratch
	@echo   upgrade           Upgrade all dependencies
	@echo   clean             Cleanup temporary build artifacts
	@echo   destroy           Destroy the virtual environment
	@echo   mypy              Run mypy
	@echo   pyright           Run pyright
	@echo   type-check        Run all type checking
	@echo   pre-commit        Runs pre-commit hooks
	@echo   lint              Run all linting
	@echo   coverage          Run tests and generate coverage report
	@echo   test              Run the tests
	@echo   fix               Run ruff to auto-fix issues
	@echo   check             Run all linting and tests
	@echo   check-all         Run all linting, tests, and coverage checks
	@echo   compose           Manage docker compose services
	@echo   docs-clean        Dump the existing built docs
	@echo   docs-build        Build documentation
	@echo   docs-serve        Serve the docs locally
	@echo.
else
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
endif

# =============================================================================
# Developer Utils
# =============================================================================

.PHONY: sync
sync:					## Sync dependencies
	@echo $(INFO) Syncing dependencies...
	uv sync --dev
	@echo $(OK) Dependencies synced

.PHONY: install
install: destroy clean			## Install dependencies
	@echo $(INFO) Starting fresh installation...
ifeq ($(IS_WINDOWS),1)
	uv venv -p 3.12
	@echo $(OK) Virtual environment created
	@if exist uv.lock ( \
		echo $(INFO) uv.lock found, syncing in locked mode... && \
		uv sync --dev --locked \
	) else ( \
		echo $(INFO) uv.lock not found, syncing without lock... && \
		uv sync --dev \
	)
else
	@if uv venv -p 3.12; then \
		echo "$(OK) Virtual environment created ✨"; \
	else \
		echo "$(ERROR) Failed to create virtual environment ❌" >&2; \
		exit 1; \
	fi
	@if [ -f uv.lock ]; then \
		echo "$(INFO) uv.lock found, syncing in locked mode... 🔒"; \
		uv sync --dev --locked; \
	else \
		echo "$(INFO) uv.lock not found, syncing without lock... 🚀"; \
		uv sync --dev; \
	fi
endif
	@echo $(OK) Installation complete

.PHONY: lock
lock:					## Rebuild lockfiles from scratch
	@echo $(INFO) Rebuilding lockfiles from scratch...
ifeq ($(IS_WINDOWS),1)
	uv lock --upgrade
	@echo $(OK) Lockfiles rebuilt
else
	@if uv lock --upgrade; then \
		echo "$(OK) Lockfiles rebuilt and updated to latest versions ✨"; \
	else \
		echo "$(ERROR) Failed to rebuild lockfiles ❌" >&2; \
		exit 1; \
	fi
endif

.PHONY: upgrade
upgrade:				## Upgrade all dependencies
	@echo $(INFO) Updating all dependencies...
	$(MAKE) lock
	$(MAKE) sync
	@echo $(INFO) Updating pre-commit hooks...
ifeq ($(IS_WINDOWS),1)
	uv run pre-commit autoupdate
	@echo $(OK) Pre-commit hooks updated
else
	@if uv run pre-commit autoupdate; then \
		echo "$(OK) Pre-commit hooks updated ✨"; \
	else \
		echo "$(ERROR) Failed to update pre-commit hooks ❌" >&2; \
		exit 1; \
	fi
endif

.PHONY: clean
clean:					## Cleanup temporary build artifacts
	@echo $(INFO) Cleaning working directory...
ifeq ($(IS_WINDOWS),1)
	@if exist .pytest_cache rd /s /q .pytest_cache
	@if exist tests\.pytest_cache rd /s /q tests\.pytest_cache
	@if exist .ruff_cache rd /s /q .ruff_cache
	@if exist .mypy_cache rd /s /q .mypy_cache
	@if exist .hypothesis rd /s /q .hypothesis
	@if exist build rd /s /q build
	@if exist dist rd /s /q dist
	@if exist .eggs rd /s /q .eggs
	@if exist .coverage del /q .coverage
	@if exist coverage.xml del /q coverage.xml
	@if exist coverage.json del /q coverage.json
	@if exist htmlcov rd /s /q htmlcov
	@if exist .unasyncd_cache rd /s /q .unasyncd_cache
	@if exist .auto_pytabs_cache rd /s /q .auto_pytabs_cache
	@if exist node_modules rd /s /q node_modules
	@for /d /r . %%d in (*.egg-info) do @if exist "%%d" rd /s /q "%%d"
	@del /s /q *.egg 2>nul
	@del /s /q *.pyc 2>nul
	@del /s /q *.pyo 2>nul
	@del /s /q *~ 2>nul
	@for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
	@for /d /r . %%d in (.ipynb_checkpoints) do @if exist "%%d" rd /s /q "%%d"
else
	@rm -rf .pytest_cache tests/.pytest_cache tests/**/.pytest_cache
	@rm -rf .ruff_cache .mypy_cache .hypothesis build/ dist/ .eggs/
	@rm -rf .coverage coverage.xml coverage.json htmlcov/
	@rm -rf .unasyncd_cache/ .auto_pytabs_cache node_modules
	@find . -name '*.egg-info' -exec rm -rf {} +
	@find . -type f -name '*.egg' -exec rm -f {} +
	@find . -name '*.pyc' -exec rm -f {} +
	@find . -name '*.pyo' -exec rm -f {} +
	@find . -name '*~' -exec rm -f {} +
	@find . -name '__pycache__' -exec rm -rf {} +
	@find . -name '.ipynb_checkpoints' -exec rm -rf {} +
endif
	$(MAKE) docs-clean
	@echo $(OK) Working directory cleaned

.PHONY: destroy
destroy:				## Destroy the virtual environment
	@echo $(INFO) Destroying virtual environment...
ifeq ($(IS_WINDOWS),1)
	@if exist .venv rd /s /q .venv
else
	@rm -rf .venv
endif
	@echo $(OK) Virtual environment destroyed

# =============================================================================
# Docker Compose
# =============================================================================

COMPOSE_DEFAULT_SERVICE := app
COMPOSE_ARGS := $(filter-out compose,$(MAKECMDGOALS))
COMPOSE_COMMAND := $(word 1,$(COMPOSE_ARGS))
COMPOSE_SERVICE := $(or $(word 2,$(COMPOSE_ARGS)),$(COMPOSE_DEFAULT_SERVICE))
COMPOSE_COMMANDS := build init up down restart logs ps pull

ifeq ($(firstword $(MAKECMDGOALS)),compose)
$(eval .PHONY: $(COMPOSE_ARGS))
$(eval $(COMPOSE_ARGS):;@:)
endif

.PHONY: compose
compose:				## Show Docker Compose commands
ifeq ($(COMPOSE_COMMAND),)
	@echo "Usage:"
	@echo "  make compose <command>"
	@echo
	@echo "Default service:"
	@echo "  $(COMPOSE_DEFAULT_SERVICE)"
	@echo
	@echo "Commands:"
	@echo "  build       Build the default service image"
	@echo "  init        Run database migrations with the default service image"
	@echo "  up          Start the default service"
	@echo "  down        Stop Docker Compose services"
	@echo "  restart     Restart the default service"
	@echo "  logs        Tail default service logs"
	@echo "  ps          List Docker Compose services"
	@echo "  pull        Pull the default service image"
else ifeq ($(filter $(COMPOSE_COMMAND),$(COMPOSE_COMMANDS)),)
	$(error Unsupported compose command "$(COMPOSE_COMMAND)". Use one of: $(COMPOSE_COMMANDS))
else ifeq ($(COMPOSE_COMMAND),build)
	@echo $(INFO) Building Docker Compose service $(COMPOSE_SERVICE)...
	docker compose build $(COMPOSE_SERVICE)
	@echo $(OK) Docker Compose service built
else ifeq ($(COMPOSE_COMMAND),init)
	@echo $(INFO) Initializing Docker Compose services...
	docker compose run --rm $(COMPOSE_DEFAULT_SERVICE) uv run app database upgrade --no-prompt
	@echo $(OK) Initializing Docker Compose services completed
else ifeq ($(COMPOSE_COMMAND),up)
	@echo $(INFO) Starting Docker Compose service $(COMPOSE_SERVICE)...
	docker compose up -d $(COMPOSE_SERVICE)
	@echo $(OK) Docker Compose service started
else ifeq ($(COMPOSE_COMMAND),down)
	@echo $(INFO) Stopping Docker Compose services...
	docker compose down
	@echo $(OK) Docker Compose services stopped
else ifeq ($(COMPOSE_COMMAND),restart)
	@echo $(INFO) Restarting Docker Compose service $(COMPOSE_SERVICE)...
	docker compose down
	docker compose up -d $(COMPOSE_SERVICE)
	@echo $(OK) Docker Compose service restarted
else ifeq ($(COMPOSE_COMMAND),logs)
	docker compose logs -f $(COMPOSE_SERVICE)
else ifeq ($(COMPOSE_COMMAND),ps)
	docker compose ps
else ifeq ($(COMPOSE_COMMAND),pull)
	@echo $(INFO) Pulling Docker Compose service image $(COMPOSE_SERVICE)...
	docker compose pull $(COMPOSE_SERVICE)
	@echo $(OK) Docker Compose service image pulled
endif

# =============================================================================
# Tests, Linting, Coverage
# =============================================================================

.PHONY: mypy
mypy:					## Run mypy
	@echo $(INFO) Running mypy...
ifeq ($(IS_WINDOWS),1)
	uv run dmypy run
	@echo $(OK) Mypy checks passed
else
	@if uv run dmypy run; then \
		echo "$(OK) Mypy checks passed ✨"; \
	else \
		echo "$(ERROR) Mypy checks failed ❌" >&2; \
		exit 1; \
	fi
endif

.PHONY: pyright
pyright:				## Run pyright
	@echo $(INFO) Running Pyright...
ifeq ($(IS_WINDOWS),1)
	uv run pyright
	@echo $(OK) Pyright checks passed
else
	@if uv run pyright; then \
		echo "$(OK) Pyright checks passed ✨"; \
	else \
		echo "$(ERROR) Pyright checks failed ❌" >&2; \
		exit 1; \
	fi
endif

.PHONY: type-check
type-check: mypy			## Run all type checking

.PHONY: pre-commit
pre-commit:				## Runs pre-commit hooks
	@echo $(INFO) Running pre-commit hooks...
ifeq ($(IS_WINDOWS),1)
	uv run pre-commit run
	@echo $(OK) Pre-commit hooks passed
else
	@if uv run pre-commit run; then \
		echo "$(OK) Pre-commit hooks passed ✨"; \
	else \
		echo "$(ERROR) Pre-commit hooks failed ❌" >&2; \
		exit 1; \
	fi
endif

.PHONY: lint
lint: pre-commit type-check		## Run all linting

.PHONY: coverage
coverage:				## Run tests and generate coverage report
	@echo $(INFO) Running tests with coverage...
ifeq ($(IS_WINDOWS),1)
	uv run pytest tests --cov -n auto
	@echo $(INFO) Generating coverage reports...
	uv run coverage html
	uv run coverage xml
	@echo $(OK) Coverage report generated
else
	@if uv run pytest tests --cov -n auto; then \
		echo "$(OK) Tests passed with coverage ✨"; \
	else \
		echo "$(ERROR) Tests failed during coverage run ❌" >&2; \
		exit 1; \
	fi
	@echo "$(INFO) Generating coverage reports... 📊"
	@uv run coverage html
	@uv run coverage xml
	@echo "$(OK) Coverage report generated in html/ and coverage.xml ✨"
endif

.PHONY: test
test:					## Run the tests
	@echo $(INFO) Running test cases...
ifeq ($(IS_WINDOWS),1)
	uv run pytest tests
	@echo $(OK) All tests passed
else
	@if uv run pytest tests; then \
		echo "$(OK) All tests passed ✨"; \
	else \
		echo "$(ERROR) Some tests failed ❌" >&2; \
		exit 1; \
	fi
endif

.PHONY: test-all
test-all: test				## Run all tests

.PHONY: fix
fix:					## Run ruff to auto-fix issues
	@echo $(INFO) Running ruff auto-fix...
ifeq ($(IS_WINDOWS),1)
	uv run ruff check src tests --fix
	@echo $(OK) Ruff auto-fix completed
else
	@if uv run ruff check src tests --fix; then \
		echo "$(OK) Ruff auto-fix completed ✨"; \
	else \
		echo "$(ERROR) Ruff auto-fix encountered issues ❌" >&2; \
		exit 1; \
	fi
endif

.PHONY: check
check: fix lint test-all		## Run all linting and tests

.PHONY: check-all
check-all: fix lint test-all coverage	## Run all linting, tests, and coverage checks

# =============================================================================
# Docs
# =============================================================================

.PHONY: docs-clean
docs-clean:				## Dump the existing built docs
	@echo $(INFO) Cleaning documentation build assets...
ifeq ($(IS_WINDOWS),1)
	@if exist docs\_build rd /s /q docs\_build
else
	@rm -rf docs/_build
endif
	@echo $(OK) Documentation build assets removed

.PHONY: docs-build
docs-build: docs-clean			## Build documentation
	@echo $(INFO) Building documentation...
ifeq ($(IS_WINDOWS),1)
	uv run sphinx-build -M html docs docs\_build -E -a -j auto --keep-going
else
	uv run sphinx-build -M html docs docs/_build -E -a -j auto --keep-going
endif
	@echo $(OK) Documentation built

.PHONY: docs-serve
docs-serve: docs-build			## Serve the docs locally
	@echo $(INFO) Starting live documentation server...
ifeq ($(IS_WINDOWS),1)
	uv run sphinx-autobuild docs docs\_build -j auto --watch src --watch docs --watch tests --open-browser --port=0 --delay 5
else
	@echo "$(INFO) Documentation built successfully, serving static files... 🚀"
	uv run sphinx-autobuild docs docs/_build -j auto --watch src --watch docs --watch tests --open-browser --port=0 --delay 5
endif
