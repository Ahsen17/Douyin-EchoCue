from datetime import UTC, datetime
from uuid import uuid4

from echocue.auth import (
    AccountCertificationModel,
    AccountCertificationStatus,
    OrganizationMemberModel,
    OrganizationMemberRole,
    OrganizationModel,
    OrganizationService,
    RoomAuthorizationModel,
    RoomAuthorizationScope,
    RoomAuthorizationStatus,
    RoomModel,
    RoomOwnershipKind,
    RoomService,
    UserModel,
)
from echocue.auth.schema import (
    AccountCertificationStruct,
    OrganizationMemberStruct,
    OrganizationStruct,
    RoomAuthorizationStruct,
    RoomStruct,
)


class TestAuthModels:
    def test_user_model_table_name_matches_database_migration(self) -> None:
        assert UserModel.__tablename__ == "user_model"

    def test_auth_model_table_names_use_domain_names(self) -> None:
        assert AccountCertificationModel.__tablename__ == "account_certification_model"
        assert OrganizationModel.__tablename__ == "organization_model"
        assert OrganizationMemberModel.__tablename__ == "organization_member_model"
        assert RoomModel.__tablename__ == "room_model"
        assert RoomAuthorizationModel.__tablename__ == "room_authorization_model"

    def test_service_repositories_bind_the_expected_models(self) -> None:
        assert OrganizationService.repository_type.model_type is OrganizationModel
        assert RoomService.repository_type.model_type is RoomModel

    def test_model_roundtrip_keeps_auth_domain_data(self) -> None:
        owner_user_id = uuid4()
        organization_id = uuid4()
        granted_by_user_id = uuid4()
        user_id = uuid4()
        started_at = datetime(2026, 8, 18, 16, 0, tzinfo=UTC)

        certification = AccountCertificationStruct(
            user_id=owner_user_id,
            status=AccountCertificationStatus.ORGANIZATION_CERTIFIED,
            organization_id=organization_id,
            certified_at=started_at,
            note="org-certified",
        )
        organization = OrganizationStruct(
            name="EchoCue Studio",
            owner_user_id=owner_user_id,
            description="primary org",
        )
        member = OrganizationMemberStruct(
            organization_id=organization_id,
            user_id=user_id,
            role=OrganizationMemberRole.ADMIN,
        )
        room = RoomStruct(
            room_id="live_room_123",
            room_kind=RoomOwnershipKind.ORGANIZATION,
            organization_id=organization_id,
        )
        grant = RoomAuthorizationStruct(
            room_id="live_room_123",
            organization_id=organization_id,
            user_id=user_id,
            access_scope=RoomAuthorizationScope.REPLAY,
            status=RoomAuthorizationStatus.ACTIVE,
            granted_by_user_id=granted_by_user_id,
            expires_at=started_at,
        )

        certification_model = AccountCertificationModel.from_struct(certification)
        organization_model = OrganizationModel.from_struct(organization)
        member_model = OrganizationMemberModel.from_struct(member)
        room_model = RoomModel.from_struct(room)
        grant_model = RoomAuthorizationModel.from_struct(grant)

        assert certification_model.__tablename__ == "account_certification_model"
        assert organization_model.__tablename__ == "organization_model"
        assert member_model.__tablename__ == "organization_member_model"
        assert room_model.__tablename__ == "room_model"
        assert grant_model.__tablename__ == "room_authorization_model"

        assert certification_model.status == "organization_certified"
        assert organization_model.name == "EchoCue Studio"
        assert member_model.role == "admin"
        assert room_model.room_kind == "organization"
        assert grant_model.access_scope == "replay"

        assert certification_model.to_struct().status is AccountCertificationStatus.ORGANIZATION_CERTIFIED
        assert organization_model.to_struct().name == "EchoCue Studio"
        assert member_model.to_struct().role is OrganizationMemberRole.ADMIN
        assert room_model.to_struct().room_kind is RoomOwnershipKind.ORGANIZATION
        assert grant_model.to_struct().access_scope is RoomAuthorizationScope.REPLAY
