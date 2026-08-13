# Configuration and Runtime Standards

This document defines constraints for configuration structure, configuration loading, environment variables, and application startup boundaries.

## Configuration Entry Points

- Read configuration uniformly through `Config.get()`.
- The default configuration file name is `config.yaml`.
- Configuration files support YAML, JSON, and TOML.
- New configuration structures belong in `aigc.base.config`.
- New configuration must be mounted on `Config`.
- Configuration structures inherit from `BaseStruct`.
- Logging configuration is exposed through `Config.logging`.

## Defaults

- Defaults should support minimal local startup.
- Path defaults should preferably be derived from `BASE_DIR` and `APP_NAME`.
- Boolean, port, timeout, connection pool, and similar settings use explicit types.
- Do not use `None` to express multiple business meanings.

## Sensitive Configuration

- Secrets, tokens, passwords, and connection strings must not be written into documentation examples or default configuration.
- Local configuration files must not be committed to the repository unless they are explicitly sanitized templates.
- Logs and exception messages must not output complete sensitive configuration.
- Tests use obviously fake values and must not reuse real accounts or connection strings.

## Environment Variables

- Environment variables required by the application runtime are set centrally in startup entry points or runtime adapter layers.
- Environment variable names use upper snake case.
- Do not scatter environment variable reads throughout business logic.
- After reading environment variables, convert them to explicit types before they enter configuration structures.

## Runtime Boundaries

- `create_app()` is responsible only for creating the Litestar application.
- Plugin registration, route assembly, logging configuration, middleware, and OpenAPI belong in the server layer.
- Routes are registered through the `controllers` aggregate.
- Plugins are registered through the `plugins` aggregate.
- Request body size is configured through `AppConfig.request_max_body_size_mb`.
- Startup entry points may set the runtime environment, but must not carry business logic.
- Command-line entry points may print startup failure messages; runtime logging must not use `print`.
- When changing the startup flow, confirm that the `app` script entry point remains usable.

## Plugins and Dependency Injection

- Runtime capability extensions are implemented by default in `src/aigc/server/plugin` and aggregated in `plugins`.
- Global dependency assembly, authentication, middleware, Store, and third-party framework integration belong to server plugin responsibility.
- Business controllers do not register global dependencies directly and do not modify application-level configuration directly.
- Use other registration approaches only when plugin lifecycle or scope does not fit, while keeping entry points centralized.
