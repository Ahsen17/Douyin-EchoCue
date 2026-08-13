# Project Command Standards

This document defines constraints for command entry points used during development, testing, migration, runtime, and documentation builds.

## Basic Principles

- Prefer project-wrapped commands instead of invoking lower-level tools directly.
- Check help information before performing unfamiliar tasks.
- When existing `app` or `make` entry points exist, do not bypass the project wrappers.
- Invoke lower-level tools directly only when the project does not provide a wrapper, and explain why.

## Help Entry Points

- View application commands with `uv run app --help`.
- View subcommands with `uv run app <command> --help`.
- View database commands with `uv run app database --help`.
- View Make targets with `make` or `make help`.
- `make --help` only displays GNU Make's own help and is not a project target index.

## Common Boundaries

- Use `uv run app database ...` for database migrations.
- Prefer `make test`, `make lint`, and `make check` for tests and quality checks.
- Prefer `make sync` for dependency synchronization.
- Prefer `make docs-build` for documentation builds.
- Prefer `uv run app run` or the project-conventional entry point for running the application.

## Prohibited Practices

- Do not execute raw Alembic commands directly as a substitute for `app database`.
- Do not bypass the Makefile to run already-wrapped batch quality checks directly.
- Do not document one-off local commands as long-term standards.
