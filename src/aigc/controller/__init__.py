from .auth import AuthController
from .system import SystemController

__all__ = (
    "AuthController",
    "SystemController",
)


controllers = (AuthController, SystemController)
