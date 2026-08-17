from pathlib import Path

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
