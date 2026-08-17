"""Authentication user persistence models.

This module defines database mappings for user authentication data.
Models are used only for persistence and are not returned directly from controllers.
"""

from advanced_alchemy.types.password_hash.base import PasswordHash
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from echocue.shared import CustomModel

from .password import password_hasher
from .schema import UserStruct

__all__ = ("UserModel",)


class UserModel(CustomModel[UserStruct]):
    """User persistence model."""

    __struct_type__ = UserStruct

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(PasswordHash(password_hasher))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
