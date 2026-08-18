"""Authentication domain enums."""

from enum import StrEnum, auto

__all__ = (
    "AccountCertificationStatus",
    "OrganizationMemberRole",
    "RoomAuthorizationScope",
    "RoomAuthorizationStatus",
    "RoomOwnershipKind",
)


class AccountCertificationStatus(StrEnum):
    """Certification state for a platform account."""

    UNCERTIFIED = auto()
    """The account has not completed certification."""

    PERSONAL_CERTIFIED = auto()
    """The account is certified for a personal live room."""

    ORGANIZATION_CERTIFIED = auto()
    """The account is certified for organization management."""


class OrganizationMemberRole(StrEnum):
    """Member roles within an organization."""

    OWNER = auto()
    """The owner has full control over the organization."""

    ADMIN = auto()
    """The admin can manage most organization resources."""

    MEMBER = auto()
    """The member has normal organization access."""

    VIEWER = auto()
    """The viewer has read-only organization access."""


class RoomOwnershipKind(StrEnum):
    """Ownership kind for a live room."""

    PERSONAL = auto()
    """The room belongs to a personal account."""

    ORGANIZATION = auto()
    """The room belongs to an organization account."""


class RoomAuthorizationStatus(StrEnum):
    """Lifecycle state for a room authorization grant."""

    PENDING = auto()
    """The grant has been created but is not yet active."""

    ACTIVE = auto()
    """The grant is active and can be used for access checks."""

    REVOKED = auto()
    """The grant has been revoked and should not be used."""


class RoomAuthorizationScope(StrEnum):
    """Permission scopes granted for a room."""

    VIEW = auto()
    """The grant allows viewing room data."""

    CONFIGURE = auto()
    """The grant allows editing room configuration."""

    REPLAY = auto()
    """The grant allows viewing room replay data."""

    START = auto()
    """The grant allows starting the room assistant."""
