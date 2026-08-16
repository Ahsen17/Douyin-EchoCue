"""Lexicon CLI plugin for Litestar."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import rich_click as click
from litestar.plugins import CLIPluginProtocol

from aigc.base import Config
from aigc.base.config.constants import BASE_DIR
from aigc.core.live.classifier import QdrantSemanticClassificationClient
from aigc.core.live.classifier.lexicon import (
    DEFAULT_LEXICON_COLLECTION_NAME,
    rebuild_lexicon_collection,
)
from aigc.core.live.classifier.rpc import create_live_classification_grpc_server
from aigc.lib import QdrantClientFactory

if TYPE_CHECKING:
    from click import Group

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
            client,
            samples_file=samples_file,
            collection_name=collection_name,
        )
        await client.close()
        click.echo(f"Rebuilt {result.collection_name} with {result.sample_count} lexicon samples.")

    asyncio.run(run())


@lexicon_group.command(name="serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="gRPC bind host.")
@click.option("--port", default=50051, show_default=True, type=int, help="gRPC bind port.")
@click.option(
    "--collection-name",
    default=DEFAULT_LEXICON_COLLECTION_NAME,
    show_default=True,
    help="Qdrant collection name used for sparse lexicon retrieval.",
)
def serve_lexicon(host: str, port: int, collection_name: str) -> None:
    """Serve live lexicon classification over gRPC."""

    async def run() -> None:
        qdrant_client = QdrantClientFactory(Config.get().qdrant).new()
        classification_client = QdrantSemanticClassificationClient(
            qdrant_client,
            collection_name=collection_name,
        )
        server = create_live_classification_grpc_server(classification_client)
        bind_address = f"{host}:{port}"
        server.add_insecure_port(bind_address)
        await server.start()
        click.echo(f"Serving live lexicon classification gRPC on {bind_address}.")
        try:
            await server.wait_for_termination()
        finally:
            await server.stop(grace=1)
            await qdrant_client.close()

    asyncio.run(run())


class LexiconPlugin(CLIPluginProtocol):
    """Register lexicon commands on Litestar's root command group."""

    def on_cli_init(self, cli: "Group") -> None:
        """Register lexicon commands."""

        cli.add_command(lexicon_group)
