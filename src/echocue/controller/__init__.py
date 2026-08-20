from .auth import AuthController
from .client import ClientController
from .system import SystemController
from .webui import WebuiController

__all__ = (
    "AuthController",
    "ClientController",
    "SystemController",
    "WebuiController",
)


controllers = (
    AuthController,
    ClientController,
    SystemController,
    WebuiController,
)
