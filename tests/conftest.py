from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

import pytest
from litestar import Litestar
from litestar.di import Provide
from litestar.exceptions import HTTPException, ValidationException
from litestar.stores.memory import MemoryStore
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from echocue.auth.model import UserModel
from echocue.auth.security import create_auth
from echocue.base import AlchemyConfig, Config
from echocue.controller.auth import AuthController
from echocue.controller.system import SystemController
from echocue.shared import ApplicationError
from echocue.shared.context import provide_request_context
from echocue.shared.exception import (
    app_error_handler,
    http_exception_handler,
    internal_exception_handler,
    validation_exception_handler,
)


@pytest.fixture(name="test_config")
async def _test_config(tmp_path: Path, monkeypatch: MonkeyPatch) -> AsyncGenerator[Config, None]:
    database_path = tmp_path / "test.sqlite3"
    config = Config(
        alchemy=AlchemyConfig(
            url=f"sqlite+aiosqlite:///{database_path}",
            pool_disabled=True,
        )
    )

    monkeypatch.setattr(Config, "get", classmethod(lambda cls, filename="config.yaml": config))

    engine = config.alchemy.async_engine
    async with engine.begin() as connection:
        await connection.run_sync(UserModel.metadata.create_all)

    try:
        yield config
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(UserModel.metadata.drop_all)

        await engine.dispose()


@pytest.fixture
async def sqlite_engine(test_config: Config) -> AsyncEngine:
    return test_config.alchemy.async_engine


@pytest.fixture
def create_test_user(test_config: Config) -> Callable[..., Awaitable[UserModel]]:
    async def _create_user(
        username: str = "admin",
        password: str = "admin",
        email: str | None = None,
        is_active: bool = True,
        is_superuser: bool = False,
    ) -> UserModel:
        session_factory = async_sessionmaker(test_config.alchemy.async_engine, expire_on_commit=False)

        async with session_factory() as session:
            user = UserModel(
                username=username,
                email=email,
                password_hash=password,
                is_active=is_active,
                is_superuser=is_superuser,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            return user

    return _create_user


@pytest.fixture
def app(test_config: Config) -> Litestar:
    return Litestar(
        route_handlers=[AuthController, SystemController],
        dependencies={"ctx": Provide(provide_request_context)},
        exception_handlers={
            ApplicationError: app_error_handler,
            ValidationException: validation_exception_handler,
            HTTPException: http_exception_handler,
            Exception: internal_exception_handler,
        },
        on_app_init=[create_auth(test_config.auth).on_app_init],
        stores={test_config.auth.session_store_name: MemoryStore()},
    )
