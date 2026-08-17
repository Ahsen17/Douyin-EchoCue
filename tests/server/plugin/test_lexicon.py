import rich_click as click
from click.testing import CliRunner
from litestar.config.app import AppConfig
from pytest import MonkeyPatch

from aigc.base import Config, LexiconConfig
from aigc.core.lexicon import FakeSemanticClassificationClient, GrpcSemanticClassificationClient
from aigc.core.live import CommentWindowHandler
from aigc.server.plugin.lexicon import LexiconPlugin, _resolve_cli_str_option


def test_lexicon_cli_option_resolver_prefers_config_when_option_uses_default() -> None:
    @click.command()
    @click.option("--host", default="127.0.0.1", show_default=True)
    @click.pass_context
    def command(ctx: click.Context, host: str) -> None:
        click.echo(_resolve_cli_str_option(ctx, "host", host, "0.0.0.0"))

    result = CliRunner().invoke(command)

    assert result.exit_code == 0
    assert result.output.strip() == "0.0.0.0"


def test_lexicon_cli_option_resolver_prefers_command_line_value() -> None:
    @click.command()
    @click.option("--host", default="127.0.0.1", show_default=True)
    @click.pass_context
    def command(ctx: click.Context, host: str) -> None:
        click.echo(_resolve_cli_str_option(ctx, "host", host, "0.0.0.0"))

    result = CliRunner().invoke(command, ["--host", "127.0.0.2"])

    assert result.exit_code == 0
    assert result.output.strip() == "127.0.0.2"


def test_lexicon_plugin_registers_fake_classification_dependencies_by_default(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "get", classmethod(lambda cls: Config()))
    app_config = LexiconPlugin().on_app_init(AppConfig())

    classification_client = app_config.state.get("semantic_classification_client")
    comment_window_handler = app_config.state.get("comment_window_handler")

    assert isinstance(classification_client, FakeSemanticClassificationClient)
    assert isinstance(comment_window_handler, CommentWindowHandler)
    assert "semantic_classification_client" in app_config.dependencies
    assert "comment_window_handler" in app_config.dependencies


def test_lexicon_plugin_registers_grpc_classification_dependencies(monkeypatch: MonkeyPatch) -> None:
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
