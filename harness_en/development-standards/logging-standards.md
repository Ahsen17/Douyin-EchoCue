# Logging Standards

This document defines constraints for application logging configuration, log output, and request logging middleware. Logging implementation uses `LoggingConfig` and `LoggingSetup` as entry points.

## Configuration Entry Points

- Logging configuration belongs in `aigc.base.config.logging`.
- Logging configuration is aggregated through `Config.logging`.
- Logging structures inherit from `BaseStruct`.
- Logging runtime adapters belong in `aigc.shared.logging`.
- Litestar logging configuration and request logging middleware are created by `LoggingSetup`.

## Output Format

- Local development uses `console` by default.
- Use `json` for machine consumption, production collection, or integration with logging platforms.
- Log level is controlled by `LoggingConfig.level`.
- Traceback depth is controlled by `traceback_depth`.
- Use `suppress_modules` when third-party module stack frames need to be hidden.

## File Logging

- File logging is disabled by default.
- When file logging is enabled, configure the path, rotation policy, and retention count through `LoggingFileConfig`.
- Log path directories are created by the logging adapter layer.
- Log files must not be written into the repository.

## Request Logging

- Request logging middleware is registered centrally by the server layer.
- Use `exclude_paths` when health checks, documentation, or static paths need to be excluded.
- Do not duplicate generic request access logging in controllers or services.

## Security Rules

- Logs must not output passwords, tokens, secrets, connection strings, or complete sensitive configuration.
- Exception logs must not expose sensitive values from local variables.
- Business logs should express context with structured fields, not by concatenating large unstructured strings.
