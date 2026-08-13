# Database and Migration Standards

This document defines constraints for database migrations and data safety. ORM model, service, and repository binding rules are governed by the ORM and Data Model Standards.

## Migration Rules

- Table structure changes must be accompanied by migrations.
- Migration scripts belong in `src/aigc/db/migrations`.
- Migration generation, checks, upgrades, and rollbacks use `uv run app database ...`.
- Before running migration tasks, check `uv run app database --help`.
- Migration names should express the intended business change.
- Migrations should execute reliably on both empty databases and existing databases.
- When ORM uses custom database types, migration templates and migration scripts must import and register the corresponding type aliases in sync.
- Do not bypass migrations to modify production table structures directly.
- Do not execute raw Alembic commands directly as a substitute for the project CLI.
- Data repair migrations should be idempotent or state explicit preconditions.
- `src/aigc/db` is currently excluded from Mypy checks; migration code still needs to remain readable, runnable, and clear in its typing boundaries.

## Data Safety

- Passwords, tokens, secrets, and connection strings must not be written in plain text into migrations, fixtures, or test data.
- External VOs do not directly expose internal audit fields, soft-delete fields, or sensitive credentials.
- Deletion strategy must state clearly whether it is hard deletion, soft deletion, or status deactivation.
