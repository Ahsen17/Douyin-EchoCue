from dataclasses import dataclass

from litestar.config.app import AppConfig
from litestar.config.cors import CORSConfig
from litestar.exceptions import HTTPException, ValidationException
from litestar.openapi.config import OpenAPIConfig

from echocue.base import Config
from echocue.controller import controllers
from echocue.shared import ApplicationError, LoggingSetup
from echocue.shared.exception import (
    app_error_handler,
    http_exception_handler,
    internal_exception_handler,
    validation_exception_handler,
)

from . import plugin
from .plugin import plugins

__all__ = ("ApplicationCore",)


@dataclass
class ApplicationCore(AppConfig):
    """Application core config."""

    def __post_init__(self) -> None:
        self.setup()

    def setup(self) -> None:
        config = Config.get()
        logging_setup = LoggingSetup(config.logging)

        self.request_max_body_size = (config.app.request_max_body_size_mb or 10) * 1024 * 1024
        self.cors_config = CORSConfig()
        self.logging_config = logging_setup.create_config()
        self.openapi_config = OpenAPIConfig(
            title="Douyin-EchoCue API",
            version="",
            path="/docs",
            render_plugins=[plugin.ScalarRenderPlugin(path="/docs")],
            enabled_endpoints={"openapi.json"},
        )

        self.exception_handlers.update(
            {
                ApplicationError: app_error_handler,
                ValidationException: validation_exception_handler,
                HTTPException: http_exception_handler,
                Exception: internal_exception_handler,
            }
        )
        self.middleware.extend(
            [
                logging_setup.create_middleware().middleware,
            ]
        )
        self.plugins.extend(plugins)
        self.route_handlers.extend(controllers)
