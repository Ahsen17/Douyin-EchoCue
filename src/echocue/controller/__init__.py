from .auth import AuthController
from .client import ClientController
from .system import SystemController

__all__ = (
    "AuthController",
    "ClientController",
    "SystemController",
)


controllers = (
    AuthController,
    ClientController,
    SystemController,
)
