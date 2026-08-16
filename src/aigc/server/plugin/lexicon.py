"""Lexicon CLI plugin for Litestar."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, cast

import rich_click as click
from litestar.plugins import CLIPluginProtocol

from aigc.base import Config
from aigc.base.config.constants import BASE_DIR
from aigc.core.live.lexicon import (
    DEFAULT_LEXICON_COLLECTION_NAME,
    rebuild_lexicon_collection,
)
from aigc.lib import QdrantClientFactory

if TYPE_CHECKING:
    from click import Group

    from aigc.core.live import SemanticQdrantClient

__all__ = ("LexiconPlugin",)


@click.group(name="lexicon")
def lexicon_group() -> None:
    """Manage live classification lexicons."""


@lexicon_group.command(name="rebuild")
@click.option(
    "--samples-file",
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
    default=BASE_DIR / "assets/live/lexicon_samples.jsonl",
    show_default=True,
    help="JSONL lexicon samples used to rebuild the sparse collection.",
)
@click.option(
    "--collection-name",
    default=DEFAULT_LEXICON_COLLECTION_NAME,
    show_default=True,
    help="Qdrant collection name to recreate.",
)
def rebuild_lexicon(samples_file: Path, collection_name: str) -> None:
    """Rebuild the live lexicon Qdrant collection."""

    async def run() -> None:
        client = QdrantClientFactory(Config.get().qdrant).new()
        result = await rebuild_lexicon_collection(
            cast("SemanticQdrantClient", client),
            samples_file=samples_file,
            collection_name=collection_name,
        )
        await client.close()
        click.echo(f"Rebuilt {result.collection_name} with {result.sample_count} lexicon samples.")

    asyncio.run(run())


class LexiconPlugin(CLIPluginProtocol):
    """Register lexicon commands on Litestar's root command group."""

    def on_cli_init(self, cli: "Group") -> None:
        """Register lexicon commands."""

        cli.add_command(lexicon_group)
