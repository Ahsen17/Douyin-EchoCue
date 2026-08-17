# Douyin-EchoCue

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Litestar-20232a.svg)](https://litestar.dev/)
[![Package Manager](https://img.shields.io/badge/package%20manager-uv-654ff0.svg)](https://docs.astral.sh/uv/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-46a2f1.svg)](https://docs.astral.sh/ruff/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

English | [简体中文](README_zh.md)

Douyin-EchoCue is a Douyin live-stream interaction assistant for hosts and operations teams.
It helps turn live chat into faster replies, more consistent prompting, and a smoother on-air interaction flow.

## Typical Scenarios

- A host wants quick, natural reply suggestions during a busy live room.
- A team wants to keep responses consistent with the room's tone and style.
- An operator wants a structured way to assist with live interaction without interrupting the show.

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


## License

This project is licensed under the [Apache License 2.0](LICENSE).
