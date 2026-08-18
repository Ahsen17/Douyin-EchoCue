"""gRPC transport skeleton for auth service."""

from typing import TYPE_CHECKING

import grpc  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from grpc import aio


def create_auth_grpc_server() -> "aio.Server":
    """Create a gRPC server for the auth service skeleton."""

    return grpc.aio.server()
