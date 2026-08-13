# General Code Standards

This document defines constraints for general code implementation. Tool configuration is governed by `pyproject.toml`, `Makefile`, and actual validation results.

## Baseline Conventions

- Python version must be at least 3.12.
- The project uses the `src` layout, and the core package name is `aigc`.
- Dependency management uses `uv`.
- Runtime dependencies are declared in `project.dependencies`.
- Development dependencies for tests, type checking, documentation, and similar tasks are declared in the corresponding dependency groups.
- Do not commit virtual environments, caches, build artifacts, secrets, or local configuration.

## Code Style

- Use Ruff for formatting and linting.
- Maximum line length is 120.
- Use spaces for indentation and LF line endings.
- Let Ruff manage import ordering.
- Use relative imports for sibling modules, for example `from .schema import UserStruct`.
- Use absolute `aigc` imports across directories.
- Parent-relative imports such as `from ..xx import ...` are forbidden.
- Variables, functions, and modules use lower snake case.
- Class names use PascalCase.
- Constants use upper snake case.
- `__all__` exports class types only.
- Functions, variables, instances, and collections must not be added to `__all__`.
- When using non-class members, import them from their original defining module path.
- Comments should explain reasons, constraints, or non-obvious behavior only.
- Do not keep debug output, temporary code, unused branches, or obsolete commented-out code.

## Docstrings and Blank Lines

- Regular Python modules should declare a module-level docstring at the top.
- `__init__.py` does not need a module-level docstring when it only aggregates package exports.
- Code docstrings use English by default.
- Module docstrings describe module responsibility, layer boundaries, and key constraints.
- Simple modules may use a one-line docstring.
- Use multi-line docstrings when external frameworks, databases, authentication, security, or other boundaries are involved.
- Module docstrings must not include author, date, or change history, and must not repeat the file name.
- Classes, public methods, and public functions must have clear docstrings.
- Method implementation order is: declaration line, docstring, blank line, implementation.
- Separate different processing steps within the same function with blank lines.
- Do not cram variable preparation, validation branches, exception handling, and return construction together.
- Docstrings describe responsibility or behavior; they do not restate type annotations.

## Typing Standards

- New code must remain fully typed.
- Public functions, methods, class attributes, and return values must provide type annotations.
- Do not use `Any` when an accurate type can express the value.
- Imports needed only for type checking belong under `if TYPE_CHECKING:`.
- Prefer Python 3.12 type parameter syntax for generics.
- Do not use `type: ignore` as a routine solution; when it is necessary, state the specific reason.

## Async and Resource Management

- Prefer asynchronous libraries for I/O operations.
- Do not execute long-running blocking calls inside async functions.
- Use database services through async context managers.
- Close resources through context managers or `finally` branches.
- Background tasks must have an explicit error handling strategy.

## Error Handling and Logging

- Do not use bare `except`.
- Narrow the exception type range when catching exceptions.
- Catch exceptions only when the code can recover, convert the error, or add useful context.
- External error messages must not include secrets, connection strings, stack information, or internal paths.
- Custom exception messages use English by default.
- Prefer Litestar semantic exceptions for protocol, routing, authentication, and integration errors that belong to framework responsibility.
- Business-domain errors should derive specific subclasses from `ApplicationError`.
- Do not use bare `ApplicationError` to represent a specific business error.
- Do not use `print` as a runtime logging mechanism, except for startup failure messages in command-line entry points.
- Log messages use parameterized formatting.
- Logging configuration and request logging rules must follow the Logging Standards.

## Common Commands

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

Run at least `make check` before committing. If validation cannot be run, state the reason and remaining risk.
