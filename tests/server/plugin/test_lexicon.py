from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import anyio
import anyio.lowlevel
import msgspec.yaml
import pytest
import rich_click as click
from click.testing import CliRunner
from litestar.config.app import AppConfig
from pytest import MonkeyPatch

from aigc.base import Config, LexiconConfig
from aigc.core.lexicon import (
    FakeSemanticClassificationClient,
    GrpcSemanticClassificationClient,
    LexiconRebuildResultStruct,
    QdrantSemanticClassificationClient,
)
from aigc.core.live import CommentWindowHandler
from aigc.server.plugin import lexicon as lexicon_module
from aigc.server.plugin.lexicon import LexiconPlugin, _resolve_cli_str_option


class FakeQdrantClient:
    """Fake async Qdrant client used by lexicon CLI tests."""

    closed: bool

    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        """Record client close calls."""

        self.closed = True


class FakeQdrantClientFactory:
    """Fake Qdrant client factory used by lexicon CLI tests."""

    client: FakeQdrantClient

    def __init__(self, config: object) -> None:
        self.client = FakeQdrantClient()

    def new(self) -> FakeQdrantClient:
        """Return a fake Qdrant client."""

        return self.client


class FakeGrpcServer:
    """Fake gRPC server used by lexicon serve CLI tests."""

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


class TestLexiconCliOptionResolver:
    runner: CliRunner
    command: click.Command

    @pytest.fixture(autouse=True)
    def set_up(self) -> None:
        self.runner = CliRunner()

        @click.command()
        @click.option("--host", default="127.0.0.1", show_default=True)
        @click.pass_context
        def command(ctx: click.Context, host: str) -> None:
            click.echo(_resolve_cli_str_option(ctx, "host", host, "0.0.0.0"))

        self.command = command

    def test_prefers_config_when_option_uses_default(self) -> None:
        result = self.runner.invoke(self.command)

        assert result.exit_code == 0
        assert result.output.strip() == "0.0.0.0"

    def test_prefers_command_line_value(self) -> None:
        result = self.runner.invoke(self.command, ["--host", "127.0.0.2"])

        assert result.exit_code == 0
        assert result.output.strip() == "127.0.0.2"


class TestLexiconRebuildCommand:
    runner: CliRunner
    samples_file: Path
    rebuild_calls: list[tuple[FakeQdrantClient, Path, str]]

    @pytest.fixture(autouse=True)
    def set_up(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        self.runner = CliRunner()
        self.samples_file = tmp_path / "lexicon_samples.jsonl"
        self.samples_file.write_text(
            '{"id":"persona_praise_000001","semantic_type":"persona_praise","text":"主播今天状态太好了"}\n',
            encoding="utf-8",
        )
        self.rebuild_calls = []

        async def fake_rebuild_lexicon_collection(
            client: FakeQdrantClient,
            *,
            samples_file: Path,
            collection_name: str,
        ) -> LexiconRebuildResultStruct:
            self.rebuild_calls.append((client, samples_file, collection_name))
            return LexiconRebuildResultStruct(collection_name=collection_name, sample_count=1)

        monkeypatch.setattr(
            Config, "get", classmethod(lambda cls: Config(lexicon=LexiconConfig(collection_name="config_lexicon")))
        )
        monkeypatch.setattr(lexicon_module, "QdrantClientFactory", FakeQdrantClientFactory)
        monkeypatch.setattr(lexicon_module, "rebuild_lexicon_collection", fake_rebuild_lexicon_collection)

    def test_rebuild_uses_config_collection_name_when_option_uses_default(self) -> None:
        result = self.runner.invoke(
            lexicon_module.lexicon_group,
            ["rebuild", "--samples-file", str(self.samples_file)],
        )

        assert result.exit_code == 0
        assert result.output.strip() == "Rebuilt config_lexicon with 1 lexicon samples."
        assert self.rebuild_calls[0][1] == self.samples_file
        assert self.rebuild_calls[0][2] == "config_lexicon"
        assert self.rebuild_calls[0][0].closed is True

    def test_rebuild_prefers_command_line_collection_name(self) -> None:
        result = self.runner.invoke(
            lexicon_module.lexicon_group,
            [
                "rebuild",
                "--samples-file",
                str(self.samples_file),
                "--collection-name",
                "cli_lexicon",
            ],
        )

        assert result.exit_code == 0
        assert result.output.strip() == "Rebuilt cli_lexicon with 1 lexicon samples."
        assert self.rebuild_calls[0][2] == "cli_lexicon"


class TestLexiconServeCommand:
    runner: CliRunner
    fake_server: FakeGrpcServer
    created_clients: list[FakeQdrantClient]
    created_classifiers: list[QdrantSemanticClassificationClient]

    @pytest.fixture(autouse=True)
    def set_up(self, monkeypatch: MonkeyPatch) -> None:
        self.runner = CliRunner()
        self.fake_server = FakeGrpcServer()
        self.created_clients = []
        self.created_classifiers = []

        class TrackingQdrantClientFactory(FakeQdrantClientFactory):
            def new(factory_self) -> FakeQdrantClient:
                client = super().new()
                self.created_clients.append(client)
                return client

        class TrackingQdrantSemanticClassificationClient(QdrantSemanticClassificationClient):
            def __init__(tracking_self, qdrant_client: Any, *, collection_name: str) -> None:
                super().__init__(qdrant_client, collection_name=collection_name)
                self.created_classifiers.append(tracking_self)

        def create_fake_server(classification_client: object) -> FakeGrpcServer:
            assert classification_client is self.created_classifiers[0]
            return self.fake_server

        monkeypatch.setattr(
            Config,
            "get",
            classmethod(
                lambda cls: Config(
                    lexicon=LexiconConfig(
                        grpc_host="0.0.0.0",
                        grpc_port=50052,
                        collection_name="config_lexicon",
                    )
                )
            ),
        )
        monkeypatch.setattr(lexicon_module, "QdrantClientFactory", TrackingQdrantClientFactory)
        monkeypatch.setattr(
            lexicon_module,
            "QdrantSemanticClassificationClient",
            TrackingQdrantSemanticClassificationClient,
        )
        monkeypatch.setattr(lexicon_module, "create_live_classification_grpc_server", create_fake_server)

    def test_serve_uses_config_bind_and_collection_when_options_use_defaults(self) -> None:
        result = self.runner.invoke(lexicon_module.lexicon_group, ["serve"])

        assert result.exit_code == 0
        assert result.output.strip() == "Serving live lexicon classification gRPC on 0.0.0.0:50052."
        assert self.fake_server.bind_address == "0.0.0.0:50052"
        assert self.fake_server.started is True
        assert self.fake_server.stopped_grace == 1
        assert self.created_classifiers[0]._collection_name == "config_lexicon"
        assert self.created_clients[0].closed is True

    def test_serve_prefers_command_line_bind_and_collection(self) -> None:
        result = self.runner.invoke(
            lexicon_module.lexicon_group,
            [
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                "50053",
                "--collection-name",
                "cli_lexicon",
            ],
        )

        assert result.exit_code == 0
        assert result.output.strip() == "Serving live lexicon classification gRPC on 127.0.0.1:50053."
        assert self.fake_server.bind_address == "127.0.0.1:50053"
        assert self.created_classifiers[0]._collection_name == "cli_lexicon"


class TestLexiconPlugin:
    def test_registers_fake_classification_dependencies_by_default(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setattr(Config, "get", classmethod(lambda cls: Config()))
        app_config = LexiconPlugin().on_app_init(AppConfig())

        classification_client = app_config.state.get("semantic_classification_client")
        comment_window_handler = app_config.state.get("comment_window_handler")

        assert isinstance(classification_client, FakeSemanticClassificationClient)
        assert isinstance(comment_window_handler, CommentWindowHandler)
        assert "semantic_classification_client" in app_config.dependencies
        assert "comment_window_handler" in app_config.dependencies

    def test_registers_grpc_classification_dependencies(self, monkeypatch: MonkeyPatch) -> None:
        def get_config(cls: type[Config]) -> Config:
            return cls(
                lexicon=LexiconConfig(
                    grpc_enabled=True,
                    grpc_target="lexicon:50051",
                    grpc_timeout=2.5,
                )
            )

        monkeypatch.setattr(Config, "get", classmethod(get_config))
        app_config = LexiconPlugin().on_app_init(AppConfig())

        classification_client = app_config.state.get("semantic_classification_client")
        comment_window_handler = app_config.state.get("comment_window_handler")

        assert isinstance(classification_client, GrpcSemanticClassificationClient)
        assert isinstance(comment_window_handler, CommentWindowHandler)


class TestLexiconComposeConfig:
    compose_config: dict[str, Any]
    app_config: dict[str, Any]
    local_config: dict[str, Any]

    @pytest.fixture(autouse=True)
    def set_up(self) -> None:
        self.compose_config = _load_yaml_dict(Path("docker-compose.yaml"))
        self.app_config = _load_yaml_dict(Path("config/app.config.yaml"))
        self.local_config = _load_yaml_dict(Path("config.yaml"))

    def test_compose_lexicon_service_can_build_and_serve_grpc(self) -> None:
        services = self.compose_config["services"]
        lexicon_service = services["lexicon"]

        assert lexicon_service["image"] == "aigc-app:0.1.0"
        assert lexicon_service["command"] == ["uv", "run", "app", "lexicon", "serve"]
        assert lexicon_service["expose"] == ["50051"]
        assert lexicon_service["depends_on"]["qdrant"]["condition"] == "service_started"
        assert "./config/app.config.yaml:/app/config.yaml:ro" in lexicon_service["volumes"]
        assert "./assets:/app/assets:ro" in lexicon_service["volumes"]

    def test_compose_app_uses_lexicon_grpc_target(self) -> None:
        app_service = self.compose_config["services"]["app"]

        assert app_service["depends_on"]["lexicon"]["condition"] == "service_started"
        assert self.app_config["lexicon"]["grpc_enabled"] is True
        assert self.app_config["lexicon"]["grpc_target"] == "lexicon:50051"
        assert self.app_config["lexicon"]["grpc_host"] == "0.0.0.0"
        assert self.app_config["qdrant"]["host"] == "qdrant"

    def test_local_default_config_uses_lexicon_block(self) -> None:
        assert "classifier" not in self.local_config
        assert self.local_config["lexicon"]["grpc_enabled"] is True
        assert self.local_config["lexicon"]["grpc_target"] == "127.0.0.1:50051"


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", msgspec.yaml.decode(path.read_bytes()))
