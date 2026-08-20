"""Authentication plugin for Litestar."""

from typing import TYPE_CHECKING, cast

import anyio
import rich_click as click
from click.core import ParameterSource
from litestar.di import Provide
from litestar.plugins import CLIPluginProtocol, InitPluginProtocol
from litestar.stores.redis import RedisStore
from litestar.stores.registry import StoreRegistry
from redis.asyncio import Redis

from echocue.auth.rpc import create_auth_grpc_server
from echocue.auth.security import USER_CLIENT_GUARD_STATE_KEY, create_auth
from echocue.base import AuthConfig, Config
from echocue.core.client import ClientSessionHandler, RedisUserClientGuard

if TYPE_CHECKING:
    from click import Group
    from litestar.config.app import AppConfig
    from litestar.datastructures import State

__all__ = ("AuthPlugin",)


@click.group(name="auth")
def auth_group() -> None:
    """Manage auth service."""


@auth_group.command(name="serve")
@click.option(
    "--host",
    default=AuthConfig().grpc_host,
    show_default=True,
    help="gRPC bind host.",
)
@click.option(
    "--port",
    default=AuthConfig().grpc_port,
    show_default=True,
    type=int,
    help="gRPC bind port.",
)
@click.pass_context
def serve_auth(ctx: "click.Context", host: str, port: int) -> None:
    """Serve auth service over gRPC."""

    async def run() -> None:
        config = Config.get().auth
        bind_host = _resolve_cli_str_option(ctx, "host", host, config.grpc_host)
        bind_port = _resolve_cli_int_option(ctx, "port", port, config.grpc_port)
        server = create_auth_grpc_server()
        bind_address = f"{bind_host}:{bind_port}"
        server.add_insecure_port(bind_address)
        await server.start()
        click.echo(f"Serving auth gRPC on {bind_address}.")
        try:
            await server.wait_for_termination()
        finally:
            await server.stop(grace=1)

    anyio.run(run)


def _resolve_cli_str_option(
    ctx: "click.Context",
    option_name: str,
    cli_value: str,
    config_value: str,
) -> str:
    if ctx.get_parameter_source(option_name) is ParameterSource.COMMANDLINE:
        return cli_value

    return config_value


def _resolve_cli_int_option(
    ctx: "click.Context",
    option_name: str,
    cli_value: int,
    config_value: int,
) -> int:
    if ctx.get_parameter_source(option_name) is ParameterSource.COMMANDLINE:
        return cli_value

    return config_value


class AuthPlugin(CLIPluginProtocol, InitPluginProtocol):
    """Redis session authentication plugin."""

    client_session_handler_state_key = "client_session_handler"

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        """Register session storage and authentication middleware."""

        config = Config.get()
        redis = Redis.from_url(config.redis.dsn)
        session_store = RedisStore(
            redis=redis,
            namespace=config.auth.session_store_namespace,
            handle_client_shutdown=True,
        )
        user_client_guard = RedisUserClientGuard(redis)
        client_session_handler = ClientSessionHandler(
            user_client_guard,
            session_max_age_seconds=config.auth.session_max_age_seconds,
        )

        if app_config.stores is None:
            app_config.stores = {config.auth.session_store_name: session_store}
        elif isinstance(app_config.stores, StoreRegistry):
            app_config.stores.register(config.auth.session_store_name, session_store, allow_override=True)
        else:
            app_config.stores[config.auth.session_store_name] = session_store

        app_config.state.update(
            {
                self.client_session_handler_state_key: client_session_handler,
                USER_CLIENT_GUARD_STATE_KEY: user_client_guard,
            }
        )
        app_config.signature_namespace.update({"ClientSessionHandler": ClientSessionHandler})
        app_config.dependencies["client_session_handler"] = Provide(
            self.provide_client_session_handler,
            sync_to_thread=True,
        )

        create_auth(config.auth).on_app_init(app_config)

        return app_config

    def provide_client_session_handler(self, state: "State") -> ClientSessionHandler:
        """Return the shared client session handler."""

        return cast("ClientSessionHandler", state.get(self.client_session_handler_state_key))

    def on_cli_init(self, cli: "Group") -> None:
        """Register auth commands."""

        cli.add_command(auth_group)
