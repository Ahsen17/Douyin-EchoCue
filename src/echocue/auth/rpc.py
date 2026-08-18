"""gRPC transport for the authentication service."""

from typing import TYPE_CHECKING, Any, cast, override
from uuid import UUID

import grpc  # type: ignore[import-untyped]
from litestar.exceptions import NotAuthorizedException

from .enum import (
    AccountCertificationStatus,
    OrganizationMemberRole,
    PermissionAction,
    RoomAuthorizationScope,
    RoomAuthorizationStatus,
    RoomOwnershipKind,
)
from .handler import AuthPermissionHandler
from .proto import auth_service_pb2, auth_service_pb2_grpc
from .schema import (
    AccountCertificationStruct,
    AuthenticationResultStruct,
    LoginRequest,
    OrganizationMemberStruct,
    OrganizationStruct,
    PermissionCheckRequestStruct,
    PermissionCheckResultStruct,
    PermissionContextStruct,
    RoomAuthorizationStruct,
    RoomStruct,
    UserStruct,
)

if TYPE_CHECKING:
    from grpc import aio

__all__ = ("AuthGrpcService", "create_auth_grpc_server")


_PROTO = cast("Any", auth_service_pb2)
_PROTO_GRPC = cast("Any", auth_service_pb2_grpc)
_CERTIFICATION_STATUS_TO_PROTO: dict[AccountCertificationStatus, int] = {
    AccountCertificationStatus.UNCERTIFIED: _PROTO.CERTIFICATION_STATUS_UNCERTIFIED,
    AccountCertificationStatus.PERSONAL_CERTIFIED: _PROTO.CERTIFICATION_STATUS_PERSONAL_CERTIFIED,
    AccountCertificationStatus.ORGANIZATION_CERTIFIED: _PROTO.CERTIFICATION_STATUS_ORGANIZATION_CERTIFIED,
}
_ORGANIZATION_MEMBER_ROLE_TO_PROTO: dict[OrganizationMemberRole, int] = {
    OrganizationMemberRole.OWNER: _PROTO.ORGANIZATION_MEMBER_ROLE_OWNER,
    OrganizationMemberRole.ADMIN: _PROTO.ORGANIZATION_MEMBER_ROLE_ADMIN,
    OrganizationMemberRole.MEMBER: _PROTO.ORGANIZATION_MEMBER_ROLE_MEMBER,
    OrganizationMemberRole.VIEWER: _PROTO.ORGANIZATION_MEMBER_ROLE_VIEWER,
}
_ROOM_OWNERSHIP_KIND_TO_PROTO: dict[RoomOwnershipKind, int] = {
    RoomOwnershipKind.PERSONAL: _PROTO.ROOM_OWNERSHIP_KIND_PERSONAL,
    RoomOwnershipKind.ORGANIZATION: _PROTO.ROOM_OWNERSHIP_KIND_ORGANIZATION,
}
_ROOM_AUTHORIZATION_STATUS_TO_PROTO: dict[RoomAuthorizationStatus, int] = {
    RoomAuthorizationStatus.PENDING: _PROTO.ROOM_AUTHORIZATION_STATUS_PENDING,
    RoomAuthorizationStatus.ACTIVE: _PROTO.ROOM_AUTHORIZATION_STATUS_ACTIVE,
    RoomAuthorizationStatus.REVOKED: _PROTO.ROOM_AUTHORIZATION_STATUS_REVOKED,
}
_ROOM_AUTHORIZATION_SCOPE_TO_PROTO: dict[RoomAuthorizationScope, int] = {
    RoomAuthorizationScope.VIEW: _PROTO.ROOM_AUTHORIZATION_SCOPE_VIEW,
    RoomAuthorizationScope.CONFIGURE: _PROTO.ROOM_AUTHORIZATION_SCOPE_CONFIGURE,
    RoomAuthorizationScope.REPLAY: _PROTO.ROOM_AUTHORIZATION_SCOPE_REPLAY,
    RoomAuthorizationScope.START: _PROTO.ROOM_AUTHORIZATION_SCOPE_START,
}
_PERMISSION_ACTION_TO_PROTO: dict[PermissionAction, int] = {
    PermissionAction.VIEW: _PROTO.PERMISSION_ACTION_VIEW,
    PermissionAction.EDIT: _PROTO.PERMISSION_ACTION_EDIT,
    PermissionAction.REPLAY: _PROTO.PERMISSION_ACTION_REPLAY,
    PermissionAction.START: _PROTO.PERMISSION_ACTION_START,
}
_PROTO_TO_PERMISSION_ACTION: dict[int, PermissionAction] = {
    proto_value: action for action, proto_value in _PERMISSION_ACTION_TO_PROTO.items()
}


class AuthGrpcService(auth_service_pb2_grpc.AuthServiceServicer):
    """gRPC service adapter for authentication operations."""

    def __init__(self, handler: AuthPermissionHandler | None = None) -> None:
        self._handler = handler or AuthPermissionHandler()

    @override
    async def Authenticate(
        self,
        request: Any,
        context: "grpc.aio.ServicerContext[Any, Any]",
    ) -> Any:
        """Authenticate credentials and return the full permission context."""

        try:
            result = await self._handler.authenticate(
                LoginRequest(username=request.username, password=request.password),
            )
        except NotAuthorizedException as exc:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, exc.detail or "Authentication failed.")
            raise RuntimeError("unreachable") from exc
        except Exception as exc:
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))
            raise RuntimeError("unreachable") from exc

        return _authentication_result_to_proto(result)

    @override
    async def GetPermissionContext(
        self,
        request: Any,
        context: "grpc.aio.ServicerContext[Any, Any]",
    ) -> Any:
        """Return the permission context for a user."""

        try:
            permission_context = await self._handler.get_permission_context(UUID(request.user_id))
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid user ID.")
            raise RuntimeError("unreachable") from exc
        except NotAuthorizedException as exc:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, exc.detail or "Authentication required.")
            raise RuntimeError("unreachable") from exc
        except Exception as exc:
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))
            raise RuntimeError("unreachable") from exc

        return _PROTO.PermissionContextResponse(context=_permission_context_to_proto(permission_context))

    @override
    async def CheckPermission(
        self,
        request: Any,
        context: "grpc.aio.ServicerContext[Any, Any]",
    ) -> Any:
        """Check whether a user may perform a room action."""

        try:
            result = await self._handler.check_permission(
                PermissionCheckRequestStruct(
                    user_id=UUID(request.user_id),
                    room_id=request.room_id,
                    action=_permission_action_from_proto(request.action),
                )
            )
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid permission check request.")
            raise RuntimeError("unreachable") from exc
        except NotAuthorizedException as exc:
            await context.abort(grpc.StatusCode.UNAUTHENTICATED, exc.detail or "Authentication required.")
            raise RuntimeError("unreachable") from exc
        except Exception as exc:
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))
            raise RuntimeError("unreachable") from exc

        return _permission_check_result_to_proto(result)


def create_auth_grpc_server(handler: AuthPermissionHandler | None = None) -> "aio.Server":
    """Create a gRPC server for the auth service."""

    server = grpc.aio.server()
    _PROTO_GRPC.add_AuthServiceServicer_to_server(
        AuthGrpcService(handler),
        server,
    )
    return server


def _authentication_result_to_proto(result: AuthenticationResultStruct) -> Any:
    proto = cast("Any", auth_service_pb2)
    return proto.AuthenticateResponse(
        user=_user_to_proto(result.user),
        context=_permission_context_to_proto(result.context),
    )


def _permission_context_to_proto(context: PermissionContextStruct) -> Any:
    proto = cast("Any", auth_service_pb2)
    kwargs: dict[str, Any] = {
        "user": _user_to_proto(context.user),
        "organizations": [_organization_to_proto(organization) for organization in context.organizations],
        "memberships": [_organization_member_to_proto(membership) for membership in context.memberships],
        "rooms": [_room_to_proto(room) for room in context.rooms],
        "room_authorizations": [_room_authorization_to_proto(grant) for grant in context.room_authorizations],
    }
    if context.certification is not None:
        kwargs["certification"] = _account_certification_to_proto(context.certification)

    return proto.PermissionContext(**kwargs)


def _permission_check_result_to_proto(result: PermissionCheckResultStruct) -> Any:
    proto = cast("Any", auth_service_pb2)
    matched_scope = (
        _ROOM_AUTHORIZATION_SCOPE_TO_PROTO[result.matched_scope]
        if result.matched_scope is not None
        else _PROTO.ROOM_AUTHORIZATION_SCOPE_UNSPECIFIED
    )
    return proto.PermissionCheckResponse(
        allowed=result.allowed,
        reason=result.reason,
        matched_scope=matched_scope,
    )


def _user_to_proto(user: UserStruct) -> Any:
    proto = cast("Any", auth_service_pb2)
    return proto.User(
        id=str(user.id),
        username=user.username,
        email=user.email or "",
        is_active=user.is_active,
        is_superuser=user.is_superuser,
    )


def _account_certification_to_proto(certification: AccountCertificationStruct | None) -> Any:
    proto = cast("Any", auth_service_pb2)
    if certification is None:
        return None

    return proto.AccountCertification(
        id=str(certification.id) if certification.id is not None else "",
        user_id=str(certification.user_id),
        status=_CERTIFICATION_STATUS_TO_PROTO[certification.status],
        organization_id=str(certification.organization_id) if certification.organization_id is not None else "",
        certified_at=certification.certified_at.isoformat() if certification.certified_at is not None else "",
        revoked_at=certification.revoked_at.isoformat() if certification.revoked_at is not None else "",
        note=certification.note or "",
    )


def _organization_to_proto(organization: OrganizationStruct) -> Any:
    proto = cast("Any", auth_service_pb2)
    return proto.Organization(
        id=str(organization.id) if organization.id is not None else "",
        name=organization.name,
        owner_user_id=str(organization.owner_user_id),
        description=organization.description or "",
        is_active=organization.is_active,
    )


def _organization_member_to_proto(membership: OrganizationMemberStruct) -> Any:
    proto = cast("Any", auth_service_pb2)
    return proto.OrganizationMember(
        id=str(membership.id) if membership.id is not None else "",
        organization_id=str(membership.organization_id),
        user_id=str(membership.user_id),
        role=_ORGANIZATION_MEMBER_ROLE_TO_PROTO[membership.role],
        is_active=membership.is_active,
    )


def _room_to_proto(room: RoomStruct) -> Any:
    proto = cast("Any", auth_service_pb2)
    return proto.Room(
        id=str(room.id) if room.id is not None else "",
        room_id=room.room_id,
        room_kind=_ROOM_OWNERSHIP_KIND_TO_PROTO[room.room_kind],
        owner_user_id=str(room.owner_user_id) if room.owner_user_id is not None else "",
        organization_id=str(room.organization_id) if room.organization_id is not None else "",
        is_active=room.is_active,
    )


def _room_authorization_to_proto(grant: RoomAuthorizationStruct) -> Any:
    proto = cast("Any", auth_service_pb2)
    return proto.RoomAuthorization(
        id=str(grant.id) if grant.id is not None else "",
        room_id=grant.room_id,
        organization_id=str(grant.organization_id),
        user_id=str(grant.user_id),
        access_scope=_ROOM_AUTHORIZATION_SCOPE_TO_PROTO[grant.access_scope],
        status=_ROOM_AUTHORIZATION_STATUS_TO_PROTO[grant.status],
        granted_by_user_id=str(grant.granted_by_user_id) if grant.granted_by_user_id is not None else "",
        expires_at=grant.expires_at.isoformat() if grant.expires_at is not None else "",
        note=grant.note or "",
    )


def _permission_action_from_proto(value: int) -> PermissionAction:
    return _PROTO_TO_PERMISSION_ACTION.get(value, PermissionAction.VIEW)
