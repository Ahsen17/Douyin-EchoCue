# Project Instructions

## Project Overview

- This is a Python 3.12 project named `aigc`.
- The project uses a `src` layout, with the main package under `src/aigc`.
- Dependency and environment management use `uv`.
- The application framework is Litestar.
- The CLI entry point is `app = "aigc.asgi:entrypoint"`.
- Configuration is loaded through `Config.get()`, with `config.yaml` as the default configuration file.

## Mandatory Standards

- Only read `.codex/harness/` or `.codex/harness_en/` when the task is related to development, testing, or project code.
- For non-code tasks, do not read those directories unless the user explicitly asks for it.
- The project must strictly follow the standards under either `.codex/harness/` or `.codex/harness_en/`.
- Reading one standards directory is sufficient for task context.
- If the user does not explicitly specify which standards directory to use, read `.codex/harness/` by default.
- The standards in `.codex/harness/` and `.codex/harness_en/` are semantic mirrors. Treat them as equivalent sources of truth.
- When updating content under `.codex/harness/`, synchronously update the corresponding content under `.codex/harness_en/`.
- When updating content under `.codex/harness_en/`, synchronously update the corresponding content under `.codex/harness/`.
- The Chinese and English standards must preserve the same meaning. Directory names, file names, headings, and body content should remain semantically mapped across both directories.

## Repository Layout

- `src/aigc/base`: Base configuration, base schemas, constants, and project foundations.
- `src/aigc/shared`: Cross-domain shared capabilities, including responses, pagination, logging, context, exceptions, and database service foundations.
- `src/aigc/server`: Litestar application assembly, plugins, middleware, logging, OpenAPI setup, and route registration.
- `src/aigc/controller`: HTTP controllers and controller aggregation.
- `src/aigc/core`: Business-domain modules.
- `src/aigc/auth`: Authentication domain code currently present in the project.
- `src/aigc/db`: Database migrations and database resources.
- `src/aigc/lib`: Lightweight pure utilities unrelated to business logic.
- `tests`: Automated tests.
- `docs`: Product, architecture, and delivery documentation.
- `.codex/harness`: Chinese engineering standards and collaboration constraints.
- `.codex/harness_en`: English engineering standards and collaboration constraints.

## Development Commands

- Prefer project-wrapped commands over direct lower-level tool invocation.
- Use `uv run app --help` and `uv run app <command> --help` to inspect application commands.
- Use `uv run app database --help` before database migration work.
- Use `make` or `make help` to inspect project Make targets.
- Common commands:

```bash
make install
make sync
make fix
make lint
make test
make coverage
make check
make docs-build
```

- Before committing code, run at least `make check` when feasible.
- For ordinary code changes, run `make test` and `make lint` when feasible.
- For changes involving types, shared abstractions, databases, or response structures, also run `make type-check` and `make coverage` when feasible.
- For documentation build changes, run `make docs-build` when feasible.
- If validation cannot be run, report the reason and remaining risk.

## Code Conventions

- Follow Ruff formatting and linting rules from `pyproject.toml`.
- Keep line length at or below 120 characters.
- Use spaces for indentation and LF line endings.
- Use lower snake case for variables, functions, and modules.
- Use PascalCase for classes.
- Use upper snake case for constants.
- Use English docstrings by default.
- Keep new code fully typed.
- Prefer precise types over `Any`.
- Put type-only imports under `if TYPE_CHECKING:`.
- Prefer Python 3.12 generic type parameter syntax where appropriate.
- Do not use parent-relative imports such as `from ..xx import ...`.
- Use sibling relative imports only within the same package level.
- Use absolute `aigc` imports across directories.
- Do not use `print` for runtime logging except startup failure messages in CLI entry points.
- Do not commit virtual environments, caches, build artifacts, secrets, or local-only configuration.

## Application Boundaries

- `create_app()` should only create the Litestar application.
- Application startup, plugins, route assembly, logging configuration, middleware, and OpenAPI belong in `src/aigc/server`.
- Controllers handle routes, parameters, and responses only.
- Controllers should call services and return `GenericResponse` family responses.
- Services must not return database models directly to controllers.
- Shared code must not depend on specific business domains.
- Base code must not depend on `controller`, `server`, or `core`.
- Test helper code must not be imported by production code.

## API and Data Rules

- APIs follow RESTful resource modeling.
- Paths use lowercase kebab case.
- Path parameters use lower snake case and match route placeholders.
- External request and response fields use camel case by default.
- Successful responses use `GenericResponse`.
- Paginated responses use `GenericResponse[Pagination]`.
- Regular data structures inherit from `BaseStruct` by default.
- HTTP request and external response schemas inherit from `CamelizedBaseStruct` by default.
- Database models inherit from `CustomModel` by default.
- Use `pydantic.BaseModel` only when a framework boundary, third-party dependency, or clear validation benefit requires it.
- Do not expose secrets, connection strings, stack traces, internal paths, database models, or sensitive fields in API responses.

## Testing Rules

- Test directories should mirror the tested modules under `src/aigc`.
- Test files use the `test_` prefix.
- Test function names should describe behavior.
- Tests must not depend on execution order or shared mutable global state.
- Async code should be tested with async tests.
- External network calls must be replaced with mocks, stubs, or local fake implementations.
- Databases, Redis, and file-system resources must use isolated fixtures.
- Test-stage databases use temporary SQLite.
- Test-stage Redis uses memory mode.
- API tests use Litestar's built-in test tools and must not start network services directly.
- Prefer testing public behavior over private implementation details.

## Documentation and Standards Maintenance

- Keep `.codex/harness/` and `.codex/harness_en/` synchronized whenever either changes.
- Preserve meaning exactly when translating standards between Chinese and English.
- Use idiomatic technical English in `.codex/harness_en/`; do not translate mechanically when a better standard English term exists.
- Keep links in both standards indexes valid after renames or moves.
- When adding a new standards document, add its counterpart in the other language and update both indexes.
