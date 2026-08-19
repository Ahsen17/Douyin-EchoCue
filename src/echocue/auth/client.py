"""Authentication client boundary for main backend integrations."""

from typing import Protocol
from uuid import UUID

from echocue.base import Config

from .rpc import GrpcAuthPermissionClient
from .schema import (
    AuthenticationResultStruct,
    LoginRequest,
    PermissionCheckRequestStruct,
    PermissionCheckResultStruct,
    PermissionContextStruct,
)

__all__ = ("AuthPermissionClient",)


class AuthPermissionClient(Protocol):
    """Client boundary used by HTTP controllers and request context providers."""

    async def authenticate(self, request: LoginRequest) -> AuthenticationResultStruct:
        """Authenticate credentials and return permission context."""

    async def get_permission_context(self, user_id: UUID) -> PermissionContextStruct:
        """Return the permission context for a user."""

    async def check_permission(self, request: PermissionCheckRequestStruct) -> PermissionCheckResultStruct:
        """Check whether a user may perform a room action."""


def create_auth_permission_client() -> AuthPermissionClient:
    """Create the configured auth permission client."""

    config = Config.get().auth
    return GrpcAuthPermissionClient(config.grpc_target, timeout=config.grpc_timeout)
