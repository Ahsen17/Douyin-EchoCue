# Douyin-EchoCue

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Litestar-20232a.svg)](https://litestar.dev/)
[![Package Manager](https://img.shields.io/badge/package%20manager-uv-654ff0.svg)](https://docs.astral.sh/uv/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-46a2f1.svg)](https://docs.astral.sh/ruff/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

English | [简体中文](README_zh.md)

Douyin-EchoCue is a Python 3.12 assistant for Douyin live-stream hosts, focused on danmaku reply support and
prompting assistance. It combines Litestar, SQLAlchemy, Redis session support, structured configuration, database
migrations, and project-wrapped development commands.

## Highlights

- Litestar application entry point through `app = "echocue.asgi:entrypoint"`.
- `src` layout with clear boundaries for base, shared, server, controller, domain, and database code.
- Typed configuration loaded through `Config.get()` from `config.yaml` and runtime environment overrides.
- SQLAlchemy database integration with migration commands exposed through the project CLI.
- Makefile targets for dependency sync, linting, tests, coverage, and Docker Compose.
- Automated tests under `tests`, organized to mirror the package layout.

## Requirements

- Python 3.12
- uv
- Docker, when using the local Compose runtime
- PostgreSQL, when running the application against a local or containerized database

## Quick Start

Install dependencies:

```bash
make install
```

Inspect available project commands:

```bash
make help
uv run app --help
uv run app database --help
```

Start the application locally:

```bash
uv run app run --host 127.0.0.1 --port 8000
```

Open the health check:

```bash
curl http://127.0.0.1:8000/system/health
```

## Database

The default configuration is loaded from `config.yaml`. Update local database settings there or provide supported
runtime environment variables before starting the app.

Run migrations through the project CLI:

```bash
uv run app database upgrade --no-prompt
```

Useful inspection commands:

```bash
uv run app database show-current-revision
uv run app database history
uv run app database check
```

## Docker Compose

Build and start services:

```bash
make compose-build
make compose-up
```

Start or operate on a single service:

```bash
make compose-up SERVICE=postgres
make compose-build SERVICE=app
make compose-logs SERVICE=app
```

Stop services:

```bash
make compose-down
```

The Compose app service builds the local Docker image from `Dockerfile`. The database service uses a PostgreSQL
image directly. After a successful build, Docker-managed images can be inspected with:

```bash
docker images
```

## Common Commands

```bash
make sync          # Sync dependencies
make fix           # Apply Ruff auto-fixes
make lint          # Run linting and type checks
make test          # Run tests
make coverage      # Run tests with coverage reports
make check         # Run formatting fixes, linting, and tests
make check-all     # Run the full local quality gate
```

## Project Layout

```text
src/echocue/
  base/        Base schemas, configuration, and constants
  shared/      Cross-domain response, context, logging, and data foundations
  server/      Litestar assembly, plugins, middleware, logging, and OpenAPI setup
  controller/  HTTP controllers and route aggregation
  core/        Business-domain modules
  auth/        Authentication domain
  db/          Database migrations and database resources
  lib/         Lightweight pure utilities
tests/                Automated tests
.codex/harness/       Engineering standards in Chinese
.codex/harness_en/    Engineering standards in English
```

## Configuration

Application configuration is centralized in `Config.get()` and defaults to `config.yaml`. Runtime overrides are exposed
through `ECHOCUE_*` environment variables where supported by the configuration layer.

Do not commit local secrets, production credentials, private connection strings, or machine-specific configuration.

## Testing

Run the default test suite:

```bash
make test
```

Run coverage:

```bash
make coverage
```

API tests should use Litestar testing tools and should not start external network services directly. Databases, Redis,
and file-system resources should be isolated through fixtures.

## Development Standards

Project changes must follow the standards in `harness/` or `harness_en/`. When changing the standards themselves, keep
the Chinese and English versions synchronized.

Before submitting changes, run the strongest feasible validation for the affected area:

```bash
make check
```

For changes touching shared abstractions, database behavior, types, or response structures, also run:

```bash
make type-check
make coverage
```

## License

This project is licensed under the [Apache License 2.0](LICENSE).
