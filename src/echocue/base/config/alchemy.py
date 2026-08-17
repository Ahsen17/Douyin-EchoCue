from typing import Any

from litestar.serialization import decode_json, encode_json
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from echocue.base.schema import BaseStruct

from .constants import APP_NAME, BASE_DIR

__all__ = ("AlchemyConfig",)


class AlchemyConfig(BaseStruct):
    """Configuration for alchemy database."""

    url: str = "sqlite+aiosqlite:///:memory:"

    echo: bool = False
    echo_pool: bool = False
    pool_disabled: bool = False
    pool_max_overflow: int = 10
    pool_size: int = 5
    pool_timeout: int = 30
    pool_recycle: int = 300
    pool_pre_ping: bool = False

    migration_config: str = f"{BASE_DIR.joinpath(f'src/{APP_NAME}')}/db/migrations/alembic.ini"
    migration_path: str = f"{BASE_DIR.joinpath(f'src/{APP_NAME}')}/db/migrations"
    migration_ddl_version_table: str = "ddl_version"

    fixture_path: str = f"{BASE_DIR.joinpath(f'src/{APP_NAME}')}/db/fixtures"

    _engine_instance: "AsyncEngine | None" = None

    @property
    def async_engine(self) -> "AsyncEngine":
        return self.get_async_engine()

    def get_async_engine(self) -> "AsyncEngine":
        if self._engine_instance is not None:
            return self._engine_instance

        if self.url.startswith("postgresql+asyncpg"):
            engine = create_async_engine(
                url=self.url,
                future=True,
                json_serializer=encode_json,
                json_deserializer=decode_json,
                echo=self.echo,
                echo_pool=self.echo_pool,
                max_overflow=self.pool_max_overflow,
                pool_size=self.pool_size,
                pool_timeout=self.pool_timeout,
                pool_recycle=self.pool_recycle,
                pool_pre_ping=self.pool_pre_ping,
                pool_use_lifo=True,  # use lifo to reduce the number of idle connections
                poolclass=NullPool if self.pool_disabled else None,
            )
            """Database session factory.

            See [`async_sessionmaker()`][sqlalchemy.ext.asyncio.async_sessionmaker].
            """

            @event.listens_for(engine.sync_engine, "connect")
            def _sqla_on_connect(dbapi_connection: Any, _: Any) -> Any:  # pragma: no cover
                r"""Using msgspec for serialization of the json column values means that the
                output is binary, not `str` like `json.dumps` would output.
                SQLAlchemy expects that the json serializer returns `str` and calls `.encode()` on the value to
                turn it to bytes before writing to the JSONB column. I'd need to either wrap `serialization.to_json` to
                return a `str` so that SQLAlchemy could then convert it to binary, or do the following, which
                changes the behaviour of the dialect to expect a binary value from the serializer.
                See Also https://github.com/sqlalchemy/sqlalchemy/blob/14bfbadfdf9260a1c40f63b31641b27fe9de12a0/lib/sqlalchemy/dialects/postgresql/asyncpg.py#L934
                    pylint: disable=line-too-long

                Note: The encoder receives already-JSON-encoded bytes from SQLAlchemy
                (via ``json_serializer=encode_json``), so it must NOT call ``encode_json``
                again — that would double-encode.  It only needs to wrap the bytes in the
                PostgreSQL binary format: no prefix for ``json``, a ``\x01`` version byte
                for ``jsonb``.
                """

                def _json_encoder(bin_value: bytes) -> bytes:
                    # json binary format: raw UTF-8 text, no prefix
                    return bin_value

                def _json_decoder(bin_value: bytes) -> Any:
                    return decode_json(bin_value)

                def _jsonb_encoder(bin_value: bytes) -> bytes:
                    # jsonb binary format: \x01 version byte + raw UTF-8 text
                    return b"\x01" + bin_value

                def _jsonb_decoder(bin_value: bytes) -> Any:
                    # strip the \x01 version byte used by PostgreSQL for jsonb
                    return decode_json(bin_value[1:])

                dbapi_connection.await_(
                    dbapi_connection.driver_connection.set_type_codec(
                        "jsonb",
                        encoder=_jsonb_encoder,
                        decoder=_jsonb_decoder,
                        schema="pg_catalog",
                        format="binary",
                    ),
                )
                dbapi_connection.await_(
                    dbapi_connection.driver_connection.set_type_codec(
                        "json",
                        encoder=_json_encoder,
                        decoder=_json_decoder,
                        schema="pg_catalog",
                        format="binary",
                    ),
                )
        elif self.url.startswith("sqlite+aiosqlite"):
            engine = create_async_engine(
                url=self.url,
                future=True,
                json_serializer=encode_json,
                json_deserializer=decode_json,
                echo=self.echo,
                echo_pool=self.echo_pool,
                pool_recycle=self.pool_recycle,
                pool_pre_ping=self.pool_pre_ping,
            )
            """Database session factory.

            See [`async_sessionmaker()`][sqlalchemy.ext.asyncio.async_sessionmaker].
            """

            @event.listens_for(engine.sync_engine, "connect")
            def _sqla_on_connect(dbapi_connection: Any, _: Any) -> Any:  # pragma: no cover
                """Override the default begin statement.  The disables the built in begin execution."""
                dbapi_connection.isolation_level = None

            @event.listens_for(engine.sync_engine, "begin")
            def _sqla_on_begin(dbapi_connection: Any) -> Any:  # pragma: no cover
                """Emits a custom begin"""
                dbapi_connection.exec_driver_sql("BEGIN")
        else:
            engine = create_async_engine(
                url=self.url,
                future=True,
                json_serializer=encode_json,
                json_deserializer=decode_json,
                echo=self.echo,
                echo_pool=self.echo_pool,
                max_overflow=self.pool_max_overflow,
                pool_size=self.pool_size,
                pool_timeout=self.pool_timeout,
                pool_recycle=self.pool_recycle,
                pool_pre_ping=self.pool_pre_ping,
                pool_use_lifo=True,  # use lifo to reduce the number of idle connections
                poolclass=NullPool if self.pool_disabled else None,
            )
        self._engine_instance = engine
        return self._engine_instance
