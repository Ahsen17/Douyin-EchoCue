# Testing Standards

This document defines constraints for test case organization, test data, fixtures, and quality validation. Tests should verify behavior and prevent regressions, not only pursue coverage numbers.

## Directory Structure

The test directory mirrors the hierarchy of tested modules under `src/aigc`:

```text
tests/
  auth/
  controller/
  shared/
  base/
```

- Test files use the `test_` prefix.
- Test function names should describe behavior.
- Do not use meaningless names such as `test_1`, `test_ok`, or `test_case`.
- Cross-module common fixtures belong in `tests/conftest.py`.
- Domain-specific fixtures belong in the `conftest.py` of the corresponding test directory.

## Test Scope

Choose test types based on change risk:

- Schema: serialization, defaults, field naming, and conversion behavior.
- Service: business rules, data conversion, and exception paths.
- Controller: routes, status codes, response wrapping, and parameter binding.
- Database: model mapping, pagination, query conditions, and migration compatibility.
- Configuration: default configuration, file loading, and format compatibility.
- Regression: minimal reproductions for fixed defects.

Changes to shared foundational capabilities, databases, response structures, and configuration loading need more complete coverage. Copy or comment changes do not require new tests.

## Writing Rules

- Tests do not depend on execution order.
- Tests do not share mutable global state.
- Async code uses async tests.
- Strict type checking covers test code; test functions, fixture parameters, and test doubles also need necessary type annotations.
- External network calls must be replaced with mocks, stubs, or local fake implementations.
- External resources such as databases, Redis, and the file system must use isolated fixtures.
- Test-stage databases use temporary SQLite and must not connect to local or production databases.
- Test-stage Redis uses memory mode and must not require a real Redis service.
- API tests use Litestar's built-in test tools and do not start network services directly.
- When testing controllers, class types, and dependency injection behavior, test cases are organized by class by default.
- When test routes need to be defined, use CBV by default; use FBV only when CBV cannot cover the target.
- Prefer real tables and data through SQLite fixtures when data can be constructed that way; mock only when stable construction is not possible.
- Time-related tests use fixed times.
- Random-value tests use fixed seeds or assert stable properties.
- Assertions should verify business results, not only that a function does not raise.
- Prefer testing public behavior instead of private implementation details for coverage.

## Fixtures

- Common fixtures belong in `tests/conftest.py` or the `conftest.py` of the corresponding test directory.
- Extract fixtures only when multiple tests reuse them.
- Fixture names express the resource or state they provide.
- Fixtures must not hide key assertions.
- Fixtures that create resources must clean them up.
- Domain-specific fixtures belong in domain test directories, not in global fixtures.
- Test configuration should override `Config.get()` to avoid reading real `config.yaml`.
- Common database fixtures are responsible for creating tables, clearing tables, or destroying temporary databases.
- API test apps are used only for controller tests and assemble only the tested routes and necessary dependencies.

## Test Data

- Construct scenarios with the minimum necessary data.
- Use obviously fake values for sensitive information.
- Time fields use fixed timezone-aware `datetime` values.
- IDs, emails, names, and similar fields use readable values.
- Data for sorting or pagination tests should demonstrate ordering.
- Do not reuse real connection strings, tokens, or accounts from production configuration.
- Test users and passwords use obviously fake values; when password logic needs validation, use the real write-to-database and authentication path.

## Dependency Rules

- Runtime dependencies required by test fixtures must be declared in project dependencies or test dependencies.
- Do not compensate for missing dependencies in tests by relying on optional local services.

## Quality Gates

For regular code changes, run at least:

```bash
make test
make lint
```

For changes involving types, shared abstractions, databases, or response structures, also run:

```bash
make type-check
make coverage
```

For changes involving documentation builds, run:

```bash
make docs-build
```

If validation cannot be run, state the reason and remaining risk.
