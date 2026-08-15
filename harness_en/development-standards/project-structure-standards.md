# Project Structure Standards

This document defines constraints for directory responsibilities, module placement, layer boundaries, and import direction. Code style, data structures, command entry points, and testing rules are governed by their corresponding topic standards.

## Directory Responsibilities

- `src/aigc/base`: Project foundation capabilities, including configuration, base schemas, and constants.
- `src/aigc/shared`: Cross-domain shared capabilities, including responses, pagination, database base services, context, exceptions, and project-level abstractions.
- `src/aigc/server`: Application assembly, including Litestar configuration, plugins, middleware, logging, and OpenAPI configuration.
- `src/aigc/controller`: HTTP controllers. They handle only routes, parameters, and responses, and are aggregated through `controllers`.
- `src/aigc/core`: Business-domain code, including domain schemas, models, services, repositories, handlers, and enums.
- `src/aigc/lib`: Lightweight pure utilities unrelated to business logic.
- `src/aigc/db`: Database migrations, fixtures, and database resources.
- `tests`: Automated tests.
- `docs`: Product, architecture, and delivery documentation.
- `harness` and `harness_en`: Engineering standards and collaboration constraints.

## Placement Rules

- Single-domain business code belongs in `src/aigc/core/<domain>`.
- Multi-domain reusable code that contains business semantics belongs in a clearly named domain module under `src/aigc/core`.
- Multi-domain reusable project capabilities without business semantics belong in `src/aigc/shared`.
- Request context, response wrappers, base database services, and project-level exceptions belong in `src/aigc/shared`.
- Pure utilities that do not depend on project configuration, frameworks, databases, or business semantics belong in `src/aigc/lib`.
- HTTP APIs belong in `src/aigc/controller`.
- Application startup, plugins, and route assembly belong in `src/aigc/server`.
- Server plugins are aggregated through `plugins`, and controllers are aggregated through `controllers`.
- Global capability extensions based on dependency injection belong in `src/aigc/server/plugin` by default.
- Configuration structures belong in `src/aigc/base/config` and must be mounted on `Config`.
- Database migrations belong in `src/aigc/db/migrations`.
- Test code belongs in `tests`; test organization details follow the Testing Standards.

## Domain Modules

New business domains should combine the following modules as needed:

```text
src/aigc/core/<domain>/
  __init__.py
  schema.py
  enum.py
  model.py
  service.py
  repository.py
  handler.py
```

- `schema.py`: Domain data structures, request inputs, external VOs, and structure conversion boundaries.
- `enum.py`: Domain enumerations.
- `model.py`: Database models.
- `service.py`: ORM/database services bound to models, repositories, and transaction boundaries.
- `repository.py`: Complex query encapsulation; simple CRUD does not require a separate repository file.
- `handler.py`: Business workflow orchestration, rule decisions, external capability coordination, and in-memory state transitions.
- `__init__.py`: Stable API aggregation exports.

Domain directories are grouped by business concepts, not split into multiple top-level `core` directories by technical process. Capabilities such as events, windows, classification, and parsing that belong to the same business domain stay under one domain directory and are split with modules that have clear responsibilities.

Create `service.py` only when database models, repositories, or transaction boundaries are involved. Use `handler.py` or a more specific module name for business orchestration that does not carry ORM/database service semantics.

## Layer Boundaries

- Controllers do not read from or write to the database directly and do not carry complex business rules.
- Controllers call domain boundaries and return `GenericResponse` family responses.
- Services do not return database models to controllers.
- Handlers do not take ORM/database service responsibility; when database access is needed, go through service or repository boundaries.
- Models express only database table structure and persistence capabilities.
- Schemas express only data shape, naming mapping, and structure conversion boundaries; they do not carry business processes.
- `shared` does not depend on specific business domains.
- `base` does not depend on `controller`, `server`, or `core`.
- `server` is responsible for assembling `controllers`, `plugins`, logging, middleware, and OpenAPI.

## Import Direction

Recommended import direction:

```text
controller -> core -> shared -> base
server -> controller/shared/base
core -> shared/base
base -> standard library or third-party dependencies
```

Production code must not import test code. When circular imports appear, first adjust responsibilities or move types into `schema.py`.
