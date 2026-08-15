# Engineering Standards Index

This directory collects project engineering standards. Follow the matching topic document when performing code development, testing, configuration, data, API, or project management work.

## Directory Layout

- `development-standards`: Project structure, code style, configuration runtime, logging, command entry points, and Git management.
- `api-and-data-standards`: HTTP APIs, authentication context, schemas, responses, ORM, databases, and migrations.
- `quality-standards`: Test organization, test data, fixtures, and quality gates.

## Document Index

- [Project Structure Standards](./development-standards/project-structure-standards.md): Directory responsibilities, module placement, layer boundaries, and import direction.
- [General Code Standards](./development-standards/general-code-standards.md): Code style, docstrings, enums, typing, async resources, error handling, and logging calls.
- [Configuration and Runtime Standards](./development-standards/configuration-and-runtime-standards.md): Configuration structure, configuration loading, environment variables, and application startup boundaries.
- [Logging Standards](./development-standards/logging-standards.md): Logging configuration, output formats, file logging, request logging, and sensitive information boundaries.
- [Project Command Standards](./development-standards/project-command-standards.md): Project command entry points such as `app` and `make`, and direct use of lower-level tools.
- [Git Project Management Standards](./development-standards/git-project-management-standards.md): Branches, atomic commits, and Git metadata related project management workflows.
- [API Design Standards](./api-and-data-standards/api-design-standards.md): HTTP paths, methods, parameters, responses, and error boundaries.
- [Authentication and Request Context Standards](./api-and-data-standards/authentication-and-request-context-standards.md): User login state, sessions, current-user resolution, and request context.
- [Data Structure and Response Standards](./api-and-data-standards/data-structure-and-response-standards.md): Schemas, structure conversion, response wrapping, pagination, and Pydantic usage boundaries.
- [ORM and Data Model Standards](./api-and-data-standards/orm-and-data-model-standards.md): ORM models, database services, repository binding, and persistence boundaries.
- [Database and Migration Standards](./api-and-data-standards/database-and-migration-standards.md): Database migrations, data repairs, and data safety.
- [Testing Standards](./quality-standards/testing-standards.md): Test directory structure, test scope, fixtures, test data, and quality gates.
