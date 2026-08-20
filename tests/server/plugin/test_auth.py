from __future__ import annotations

from pathlib import Path
from typing import Any

import anyio.lowlevel
import msgspec.yaml
import pytest
import rich_click as click
from click.testing import CliRunner
from litestar.config.app import AppConfig

from echocue.base import AuthConfig, Config
from echocue.server.plugin import auth as auth_module
from echocue.server.plugin.auth import AuthPlugin


class FakeGrpcServer:
    """Fake gRPC server used by auth CLI tests."""

    bind_address: str | None
    started: bool
    stopped_grace: float | None

    def __init__(self) -> None:
        self.bind_address = None
        self.started = False
        self.stopped_grace = None

    def add_insecure_port(self, bind_address: str) -> None:
        self.bind_address = bind_address

    async def start(self) -> None:
        self.started = True

    async def wait_for_termination(self) -> None:
        await anyio.lowlevel.checkpoint()

    async def stop(self, grace: float) -> None:
        await anyio.lowlevel.checkpoint()
        self.stopped_grace = grace


class TestAuthServeCommand:
    runner: CliRunner
    fake_server: FakeGrpcServer

    @pytest.fixture(autouse=True)
    def set_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.runner = CliRunner()
        self.fake_server = FakeGrpcServer()

        monkeypatch.setattr(
            Config,
            "get",
            classmethod(
                lambda cls: Config(
                    auth=AuthConfig(
                        grpc_enabled=True,
                        grpc_target="auth:50052",
                        grpc_host="0.0.0.0",
                        grpc_port=50052,
                    )
                )
            ),
        )
        monkeypatch.setattr(auth_module, "create_auth_grpc_server", lambda: self.fake_server)

    def test_help_is_available(self) -> None:
        result = self.runner.invoke(auth_module.auth_group, ["serve", "--help"])

        assert result.exit_code == 0
        assert "gRPC bind host." in result.output

    def test_serve_uses_config_bind_when_options_use_defaults(self) -> None:
        result = self.runner.invoke(auth_module.auth_group, ["serve"])

        assert result.exit_code == 0
        assert result.output.strip() == "Serving auth gRPC on 0.0.0.0:50052."
        assert self.fake_server.bind_address == "0.0.0.0:50052"
        assert self.fake_server.started is True
        assert self.fake_server.stopped_grace == 1

    def test_serve_prefers_command_line_bind(self) -> None:
        result = self.runner.invoke(
            auth_module.auth_group,
            [
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                "50053",
            ],
        )

        assert result.exit_code == 0
        assert result.output.strip() == "Serving auth gRPC on 127.0.0.1:50053."
        assert self.fake_server.bind_address == "127.0.0.1:50053"


class TestAuthPlugin:
    def test_registers_auth_command(self) -> None:
        @click.group()
        def cli() -> None:
            pass

        AuthPlugin().on_cli_init(cli)

        assert "auth" in cli.commands

    def test_registers_session_store_dependencies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Config, "get", classmethod(lambda cls: Config()))
        app_config = AuthPlugin().on_app_init(AppConfig())

        assert app_config.stores is not None
        if isinstance(app_config.stores, dict):
            assert "sessions" in app_config.stores
        else:
            assert app_config.stores.get("sessions") is not None
        assert "client_session_handler" in app_config.state
        assert "user_client_guard" in app_config.state
        assert "client_session_handler" in app_config.dependencies


class TestAuthComposeConfig:
    compose_config: dict[str, Any]
    app_config: dict[str, Any]

    @pytest.fixture(autouse=True)
    def set_up(self) -> None:
        self.compose_config = msgspec.yaml.decode(Path("docker-compose.yaml").read_text(encoding="utf-8"))
        self.app_config = msgspec.yaml.decode(Path("config/app.config.yaml").read_text(encoding="utf-8"))

    def test_compose_auth_service_can_build_and_serve_grpc(self) -> None:
        services = self.compose_config["services"]
        auth_service = services["auth"]

        assert auth_service["image"] == "echocue:0.1.0"
        assert auth_service["command"] == ["uv", "run", "app", "auth", "serve"]
        assert auth_service["expose"] == ["50052"]
        assert auth_service["depends_on"]["postgres"]["condition"] == "service_healthy"
        assert "./config/app.config.yaml:/app/config.yaml:ro" in auth_service["volumes"]
        assert "./logs:/app/logs" in auth_service["volumes"]

    def test_compose_app_uses_auth_grpc_target(self) -> None:
        app_service = self.compose_config["services"]["app"]

        assert app_service["depends_on"]["auth"]["condition"] == "service_started"
        assert self.app_config["auth"]["grpc_enabled"] is True
        assert self.app_config["auth"]["grpc_target"] == "auth:50052"
        assert self.app_config["auth"]["grpc_host"] == "0.0.0.0"
