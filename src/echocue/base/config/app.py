from echocue.base.schema import BaseStruct

from .constants import APP_NAME

__all__ = ("AppConfig",)


class AppConfig(BaseStruct):
    """Configuration for application."""

    app_loc: str = f"{APP_NAME}.asgi:create_app"
    host: str = "localhost"
    port: int = 8000

    request_max_body_size_mb: int = 10
