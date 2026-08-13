# Project Structure Standards

This document defines constraints for directory responsibilities, module placement, and import boundaries. For new code, determine its responsibility before placing it in the corresponding directory. If ownership is unclear, clarify the domain boundary first instead of placing the code in a broad `utils` module.

## Directory Responsibilities

- `src/aigc/base`: Project foundation capabilities, including configuration, base schemas, and constants.
- `src/aigc/shared`: Cross-domain shared capabilities, including responses, pagination, database base services, and project-level abstractions.
- `src/aigc/server`: Application assembly, including Litestar configuration, plugins, logging, and OpenAPI configuration.
- `src/aigc/controller`: HTTP controllers. They handle only routes, parameters, and responses, and are aggregated through `controllers`.
- `src/aigc/core`: Business-domain code, including domain schemas, models, services, and repositories.
- `src/aigc/lib`: Lightweight pure utilities unrelated to business logic.
- `src/aigc/db`: Database migrations, fixtures, and database resources.
- `tests`: Automated tests.
- `docs`: Product, architecture, and delivery documentation.
- `harness`: Engineering standards and collaboration constraints.

## Placement Rules

- Single-domain code belongs in `src/aigc/core/<domain>`.
- Multi-domain reusable code that contains business semantics belongs in a shared domain module under `src/aigc/core`.
- Multi-domain reusable project capabilities without business semantics belong in `src/aigc/shared`.
- Runtime structures shared by cross-business interfaces, such as request context, belong in `src/aigc/shared`.
- Pure utilities that do not depend on project configuration, frameworks, databases, or business semantics belong in `src/aigc/lib`.
- HTTP APIs belong in `src/aigc/controller`.
- Application startup, plugins, and route assembly belong in `src/aigc/server`.
- Server plugins are aggregated through `plugins`, and controllers are aggregated through `controllers`.
- Global capability extensions based on dependency injection belong in `src/aigc/server/plugin` by default.
- Configuration structures belong in `src/aigc/base/config` and must be mounted on `Config`.
- Database migrations belong in `src/aigc/db/migrations`.
- Test helper code belongs in `tests` and must not be imported by production code.
- Test directories mirror the hierarchy of the tested modules under `src/aigc`.

## Domain Modules

New business domains should prefer the following structure:

```text
src/aigc/core/<domain>/
  __init__.py
  schema.py
  model.py
  service.py
  repository.py
```

- `schema.py`: Request inputs, service-layer structures, and external VOs.
- `model.py`: Database models.
- `service.py`: Business processes, rule decisions, data conversion, and transaction boundaries.
- `repository.py`: Complex query encapsulation; simple CRUD does not require a separate repository file.
- `__init__.py`: Exports only stable APIs.

## Layer Boundaries

- Controllers do not read from or write to the database directly and do not carry complex business rules.
- Controllers call services and return `GenericResponse` family responses.
- Services do not return database models to controllers.
- Models express only database table structure and persistence capabilities.
- Schemas express only data shape and do not carry business processes.
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
