from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import echocue.auth.password as password_module
from echocue.auth import (
    AccountCertificationModel,
    AccountCertificationStatus,
    AuthPermissionHandler,
    OrganizationMemberModel,
    OrganizationMemberRole,
    OrganizationModel,
    PermissionAction,
    PermissionCheckRequestStruct,
    RoomAuthorizationModel,
    RoomAuthorizationScope,
    RoomAuthorizationStatus,
    RoomModel,
    RoomOwnershipKind,
    UserDisabledError,
    UserModel,
)
from echocue.auth.schema import LoginRequest
from echocue.base import Config


@dataclass(slots=True)
class AuthGraph:
    owner: UserModel
    member: UserModel
    guest: UserModel
    organization: OrganizationModel
    organization_room: RoomModel
    personal_room: RoomModel


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(password_module.password_hasher, "iterations", 1)


async def _create_auth_graph(
    test_config: Config,
    create_test_user: Callable[..., Awaitable[UserModel]],
) -> AuthGraph:
    owner = await create_test_user(username="owner", password="owner-password")
    member = await create_test_user(username="member", password="member-password")
    guest = await create_test_user(username="guest", password="guest-password")
    session_factory = async_sessionmaker(test_config.alchemy.async_engine, expire_on_commit=False)

    async with session_factory() as session:
        organization = OrganizationModel(name="EchoCue Studio", owner_user_id=owner.id)
        session.add(organization)
        await session.flush()

        session.add_all(
            (
                AccountCertificationModel(
                    user_id=owner.id,
                    status=AccountCertificationStatus.ORGANIZATION_CERTIFIED.value,
                    organization_id=organization.id,
                ),
                AccountCertificationModel(
                    user_id=member.id,
                    status=AccountCertificationStatus.PERSONAL_CERTIFIED.value,
                ),
                OrganizationMemberModel(
                    organization_id=organization.id,
                    user_id=member.id,
                    role=OrganizationMemberRole.MEMBER.value,
                ),
            )
        )
        organization_room = RoomModel(
            room_id="org-room",
            room_kind=RoomOwnershipKind.ORGANIZATION.value,
            organization_id=organization.id,
        )
        personal_room = RoomModel(
            room_id="personal-room",
            room_kind=RoomOwnershipKind.PERSONAL.value,
            owner_user_id=guest.id,
        )
        session.add_all((organization_room, personal_room))
        await session.flush()

        session.add_all(
            (
                RoomAuthorizationModel(
                    room_id=organization_room.room_id,
                    organization_id=organization.id,
                    user_id=member.id,
                    access_scope=RoomAuthorizationScope.START.value,
                    status=RoomAuthorizationStatus.ACTIVE.value,
                    granted_by_user_id=owner.id,
                ),
                RoomAuthorizationModel(
                    room_id=personal_room.room_id,
                    organization_id=organization.id,
                    user_id=member.id,
                    access_scope=RoomAuthorizationScope.REPLAY.value,
                    status=RoomAuthorizationStatus.ACTIVE.value,
                    granted_by_user_id=owner.id,
                ),
            )
        )
        await session.commit()
        await session.refresh(organization)
        await session.refresh(organization_room)
        await session.refresh(personal_room)

    return AuthGraph(
        owner=owner,
        member=member,
        guest=guest,
        organization=organization,
        organization_room=organization_room,
        personal_room=personal_room,
    )


class TestAuthPermissionHandler:
    async def test_authenticate_returns_permission_context(
        self,
        test_config: Config,
        create_test_user: Callable[..., Awaitable[UserModel]],
    ) -> None:
        graph = await _create_auth_graph(test_config, create_test_user)
        handler = AuthPermissionHandler()

        result = await handler.authenticate(LoginRequest(username="member", password="member-password"))

        assert result.user.id == graph.member.id
        assert result.context.certification is not None
        assert result.context.certification.status is AccountCertificationStatus.PERSONAL_CERTIFIED
        assert {organization.name for organization in result.context.organizations} == {"EchoCue Studio"}
        assert {room.room_id for room in result.context.rooms} == {"org-room", "personal-room"}
        assert {grant.room_id for grant in result.context.room_authorizations} == {"org-room", "personal-room"}

    async def test_organization_owner_can_edit_owned_room_without_membership_row(
        self,
        test_config: Config,
        create_test_user: Callable[..., Awaitable[UserModel]],
    ) -> None:
        graph = await _create_auth_graph(test_config, create_test_user)
        handler = AuthPermissionHandler()

        result = await handler.check_permission(
            PermissionCheckRequestStruct(
                user_id=graph.owner.id,
                room_id="org-room",
                action=PermissionAction.EDIT,
            )
        )

        assert result.allowed is True
        assert result.reason == "Organization owner can access the room."

    async def test_member_start_permission_uses_room_grant(
        self,
        test_config: Config,
        create_test_user: Callable[..., Awaitable[UserModel]],
    ) -> None:
        graph = await _create_auth_graph(test_config, create_test_user)
        handler = AuthPermissionHandler()

        result = await handler.check_permission(
            PermissionCheckRequestStruct(
                user_id=graph.member.id,
                room_id="org-room",
                action=PermissionAction.START,
            )
        )

        assert result.allowed is True
        assert result.matched_scope is RoomAuthorizationScope.START

    async def test_invited_personal_room_allows_replay_but_not_edit(
        self,
        test_config: Config,
        create_test_user: Callable[..., Awaitable[UserModel]],
    ) -> None:
        graph = await _create_auth_graph(test_config, create_test_user)
        handler = AuthPermissionHandler()

        replay_result = await handler.check_permission(
            PermissionCheckRequestStruct(
                user_id=graph.member.id,
                room_id="personal-room",
                action=PermissionAction.REPLAY,
            )
        )
        edit_result = await handler.check_permission(
            PermissionCheckRequestStruct(
                user_id=graph.member.id,
                room_id="personal-room",
                action=PermissionAction.EDIT,
            )
        )

        assert replay_result.allowed is True
        assert replay_result.matched_scope is RoomAuthorizationScope.REPLAY
        assert edit_result.allowed is False
        assert edit_result.reason == "Personal room authorization does not cover the requested action."

    async def test_inactive_user_credentials_are_rejected(
        self,
        create_test_user: Callable[..., Awaitable[UserModel]],
    ) -> None:
        await create_test_user(username="disabled", password="password", is_active=False)
        handler = AuthPermissionHandler()

        with pytest.raises(UserDisabledError):
            await handler.authenticate(LoginRequest(username="disabled", password="password"))
