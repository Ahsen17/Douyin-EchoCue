import re
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Literal, Self

from advanced_alchemy.base import UUIDv7AuditBase
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig
from advanced_alchemy.filters import LimitOffset, OrderBy, StatementFilter
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from litestar.plugins.sqlalchemy import AlembicAsyncConfig, AsyncSessionConfig
from msgspec import convert
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import ColumnElement

from echocue.base import AlchemyConfig, BaseStruct, Config

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


__all__ = (
    "AlchemySetup",
    "CustomModel",
    "CustomService",
)


def camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class AlchemySetup:
    """Configure SQLAlchemy for Litestar"""

    def __init__(self, config: "AlchemyConfig") -> None:
        self._config = config

    @classmethod
    def from_config(cls, config: "AlchemyConfig | None" = None) -> Self:
        return cls(config or Config.get().alchemy)

    def create_config(self) -> "SQLAlchemyAsyncConfig":
        return SQLAlchemyAsyncConfig(
            engine_instance=self._config.async_engine,
            before_send_handler="autocommit",
            session_config=AsyncSessionConfig(expire_on_commit=False),
            alembic_config=AlembicAsyncConfig(
                version_table_name=self._config.migration_ddl_version_table,
                script_config=self._config.migration_config,
                script_location=self._config.migration_path,
            ),
        )


class CustomModel[T: BaseStruct](UUIDv7AuditBase):
    """Custom model base."""

    __abstract__ = True

    __struct_type__: type[T]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        cls.__tablename__ = camel_to_snake(cls.__qualname__)

    def to_struct(self) -> T:
        """Convert the model to a struct."""

        return convert(self.to_dict(), type=self.__struct_type__)

    @classmethod
    def from_struct(cls, obj: T) -> Self:
        """Convert a struct to a model."""

        return cls(**obj.to_dict())


class CustomService[T: CustomModel](SQLAlchemyAsyncRepositoryService[T]):
    """Generic database service."""

    # class _Repository(SQLAlchemyAsyncRepository[T]):
    #     """Generic repository for OrientModel"""

    #     model_type: type[T]  # noqa: ERA001

    # repository_type = _Repository  # noqa: ERA001

    async def paginate(
        self,
        *filters: StatementFilter | ColumnElement[bool],
        limit: int,
        offset: int,
        order_by: str | ColumnElement[Any] | InstrumentedAttribute[Any] = "created_at",
        order: Literal["asc", "desc"] = "asc",
    ) -> "Sequence[T]":
        """Paginate the results."""

        if offset < 0 or limit <= 0:
            raise ValueError("Invalid pagination parameters")

        return await self.list(
            *filters,
            *(
                LimitOffset(limit=limit, offset=offset),
                OrderBy(field_name=order_by, sort_order=order),
            ),
        )

    @classmethod
    @asynccontextmanager
    async def provide(
        cls,
        session: "AsyncSession | None" = None,
    ) -> AsyncGenerator[Self, None]:
        try:
            async with cls.new(
                session=session,
                config=AlchemySetup.from_config().create_config(),
            ) as service:
                yield service

        finally:
            if session:
                await session.aclose()
