# Engineering Standards Index

This directory collects all project constraints that apply to code implementation. Follow the standards in this directory strictly when performing code development, unit testing, engineering configuration changes, and related work.

## Directory Layout

- `development-standards`: Constraints for project structure, module placement, general code style, and baseline implementation rules.
- `api-and-data-standards`: Constraints for schemas, requests and responses, pagination, database models, and Pydantic usage boundaries.
- `quality-standards`: Constraints for test organization, test data, fixtures, and quality gates.

## Document Index

- [Project Structure Standards](./development-standards/project-structure-standards.md): Constraints for directory responsibilities, code module placement, layer boundaries, and import direction.
- [General Code Standards](./development-standards/general-code-standards.md): Constraints for code style, typing, asynchronous resources, error handling, and common validation commands.
- [Configuration and Runtime Standards](./development-standards/configuration-and-runtime-standards.md): Constraints for configuration structure, configuration loading, environment variables, and application startup boundaries.
- [Logging Standards](./development-standards/logging-standards.md): Constraints for logging configuration, output formats, file logging, request logging, and sensitive information boundaries.
- [Project Command Standards](./development-standards/project-command-standards.md): Constraints for project command entry points such as `app` and `make`, and for direct use of lower-level tools.
- [API Design Standards](./api-and-data-standards/api-design-standards.md): Constraints for HTTP paths, methods, parameters, responses, and error boundaries.
- [Authentication and Request Context Standards](./api-and-data-standards/authentication-and-request-context-standards.md): Constraints for user login state, Redis sessions, current-user resolution, and request context usage.
- [Data Structure and Response Standards](./api-and-data-standards/data-structure-and-response-standards.md): Constraints for using `BaseStruct`, `CamelizedBaseStruct`, `GenericResponse`, `Pagination`, `CustomModel`, and `pydantic.BaseModel`.
- [ORM and Data Model Standards](./api-and-data-standards/orm-and-data-model-standards.md): Constraints for ORM models, services, repository binding, and data object conversion.
- [Database and Migration Standards](./api-and-data-standards/database-and-migration-standards.md): Constraints for database migrations and data safety.
- [Testing Standards](./quality-standards/testing-standards.md): Constraints for test directory structure, test types, fixtures, test data, and quality gates.
