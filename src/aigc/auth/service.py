"""Authentication domain services.

This module handles user lookup, password verification, and login state checks.
Services return service-layer structs and do not expose database models to controllers.
"""

from uuid import UUID

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.types.password_hash.base import HashedPassword
from litestar.exceptions import NotAuthorizedException

from aigc.shared import CustomService

from .exception import UserDisabledError
from .model import UserModel
from .password import password_hasher
from .schema import LoginRequest, UserStruct

__all__ = ("UserService",)


class UserService(CustomService[UserModel]):
    """User database service."""

    class _Repository(SQLAlchemyAsyncRepository[UserModel]):
        """User model repository."""

        model_type: type[UserModel] = UserModel

    repository_type = _Repository

    async def get_by_id(self, user_id: UUID) -> UserStruct | None:
        """Get active or inactive user data by primary key."""

        user = await self.get_one_or_none(id=user_id)

        return user.to_struct() if user else None

    async def get_by_username(self, username: str) -> UserModel | None:
        """Get a user model by username."""

        return await self.get_one_or_none(username=username)

    async def authenticate(self, data: LoginRequest) -> UserStruct:
        """Authenticate a login request and return service-layer user data."""

        user = await self.get_by_username(data.username)

        if user is None:
            raise NotAuthorizedException(detail="Invalid username or password.")

        stored_password = user.password_hash
        password_valid = (
            stored_password.verify(data.password)
            if isinstance(stored_password, HashedPassword)
            else password_hasher.verify(data.password, stored_password)
        )

        if not password_valid:
            raise NotAuthorizedException(detail="Invalid username or password.")

        if not user.is_active:
            raise UserDisabledError()

        return user.to_struct()
