import logging
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from litestar.logging.config import LoggingConfig as LitestarLoggingConfig
from litestar.logging.config import StructLoggingConfig
from litestar.middleware.logging import LoggingMiddlewareConfig
from structlog.dev import ConsoleRenderer, RichTracebackFormatter
from structlog.processors import (
    CallsiteParameter,
    CallsiteParameterAdder,
    ExceptionRenderer,
    JSONRenderer,
    TimeStamper,
    add_log_level,
)
from structlog.stdlib import ProcessorFormatter
from structlog.tracebacks import ExceptionDictTransformer

if TYPE_CHECKING:
    from structlog.types import Processor

    from aigc.base import LoggingConfig


__all__ = ("LoggingSetup",)


_CALLSITE_PARAMETERS = (
    CallsiteParameter.PATHNAME,
    CallsiteParameter.LINENO,
    CallsiteParameter.FUNC_NAME,
)


class LoggingSetup:
    """Converts ``LoggingConfig`` into Litestar's ``StructLoggingConfig`` and ``LoggingMiddlewareConfig``."""

    def __init__(self, config: "LoggingConfig") -> None:
        self._config = config
        self._as_json = config.format == "json"

    def create_config(self) -> "StructLoggingConfig":
        """Create ``StructLoggingConfig`` with custom processors and stdlib bridge."""

        return StructLoggingConfig(
            processors=self._build_structlog_processors(),
            standard_lib_logging_config=self._build_stdlib_config(),
            wrapper_class=structlog.make_filtering_bound_logger(self._config.level),
            logger_factory=structlog.WriteLoggerFactory(),
            pretty_print_tty=not self._as_json,
            log_exceptions="always",
        )

    def create_middleware(self) -> "LoggingMiddlewareConfig":
        """Create ``LoggingMiddlewareConfig`` for HTTP request/response logging."""

        if self._config.exclude_paths:
            return LoggingMiddlewareConfig(exclude=self._config.exclude_paths)
        return LoggingMiddlewareConfig()

    def _build_structlog_processors(self) -> list["Processor"]:
        """Build structlog processor chain based on configured format."""

        chain: list[Processor] = [
            structlog.contextvars.merge_contextvars,
            add_log_level,
            CallsiteParameterAdder(parameters=_CALLSITE_PARAMETERS),
            TimeStamper(fmt="iso"),
        ]

        if self._as_json:
            chain.extend(self._json_renderers())
        else:
            chain.extend(self._console_renderers())
        return chain

    def _build_stdlib_processors(self) -> list["Processor"]:
        """Build stdlib bridge processors for ``ProcessorFormatter``."""

        chain: list[Processor] = [
            TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.stdlib.ExtraAdder(),
            ProcessorFormatter.remove_processors_meta,
        ]

        if self._as_json:
            chain.append(JSONRenderer())
        else:
            chain.append(
                ConsoleRenderer(
                    exception_formatter=RichTracebackFormatter(
                        max_frames=self._config.traceback_depth,
                        suppress=self._config.suppress_modules,
                        show_locals=False,
                    ),
                ),
            )
        return chain

    def _json_renderers(self) -> list["Processor"]:
        return [
            self._make_exception_renderer(),
            JSONRenderer(),
        ]

    def _console_renderers(self) -> list["Processor"]:
        return [
            ConsoleRenderer(
                exception_formatter=RichTracebackFormatter(
                    max_frames=self._config.traceback_depth,
                    suppress=self._config.suppress_modules,
                    show_locals=False,
                ),
            ),
        ]

    def _make_exception_renderer(self) -> "ExceptionRenderer":
        return ExceptionRenderer(
            ExceptionDictTransformer(
                max_frames=self._config.traceback_depth,
                suppress=self._config.suppress_modules,
                show_locals=False,
            ),
        )

    def _build_stdlib_config(self) -> "LitestarLoggingConfig":
        """Build stdlib ``LoggingConfig`` with handlers and ignored loggers."""

        formatter: dict[str, object] = {
            "()": ProcessorFormatter,
            "processors": self._build_stdlib_processors(),
        }

        handlers: dict[str, dict[str, object]] = {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "standard",
            },
        }

        root_handlers: list[str] = ["console"]

        if self._config.file.enabled:
            handlers["file"] = self._build_file_handler()
            root_handlers.append("file")

        loggers: dict[str, dict[str, object]] = {}
        for name in self._config.ignored_loggers:
            loggers[name] = {"level": logging.CRITICAL + 1, "handlers": [], "propagate": False}

        return LitestarLoggingConfig(
            formatters={"standard": formatter},
            handlers=handlers,
            loggers=loggers,
            root={"handlers": root_handlers, "level": self._config.level},
        )

    def _build_file_handler(self) -> dict[str, object]:
        """Build file handler dict config with rotation."""

        file_cfg = self._config.file
        Path(file_cfg.path).parent.mkdir(parents=True, exist_ok=True)

        if file_cfg.rotation == "time":
            return {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "filename": file_cfg.path,
                "when": file_cfg.when,
                "interval": file_cfg.interval,
                "backupCount": file_cfg.backup_count,
                "formatter": "standard",
                "level": "DEBUG",
            }

        return {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": file_cfg.path,
            "maxBytes": file_cfg.max_bytes,
            "backupCount": file_cfg.backup_count,
            "formatter": "standard",
            "level": "DEBUG",
        }
