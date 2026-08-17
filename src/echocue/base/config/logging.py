from typing import Literal

from msgspec import field

from echocue.base.schema import BaseStruct

__all__ = (
    "LoggingConfig",
    "LoggingFileConfig",
)


class LoggingFileConfig(BaseStruct):
    """Configuration for log file output."""

    enabled: bool = False
    path: str = "logs/app.log"
    rotation: Literal["size", "time"] = "size"
    max_bytes: int = 10_485_760
    backup_count: int = 5
    when: str = "midnight"
    interval: int = 1


class LoggingConfig(BaseStruct):
    """Configuration for application logging."""

    level: str = "INFO"
    format: Literal["console", "json"] = "console"
    traceback_depth: int = 10
    suppress_modules: list[str] = []
    ignored_loggers: list[str] = []
    exclude_paths: list[str] = []
    file: LoggingFileConfig = field(default_factory=LoggingFileConfig)
