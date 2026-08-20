from litestar.plugins import PluginProtocol

from .alchemy import AlchemyPlugin
from .auth import AuthPlugin
from .client import ClientPlugin
from .context import ContextPlugin
from .docs import ScalarRenderPlugin
from .lexicon import LexiconPlugin
from .live import LivePlugin
from .qdrant import QdrantPlugin
from .room import RoomPlugin

__all__ = (
    "AlchemyPlugin",
    "AuthPlugin",
    "ClientPlugin",
    "ContextPlugin",
    "LexiconPlugin",
    "LivePlugin",
    "QdrantPlugin",
    "RoomPlugin",
    "ScalarRenderPlugin",
)


plugins: tuple[PluginProtocol, ...] = (
    AlchemyPlugin(),
    AuthPlugin(),
    ClientPlugin(),
    ContextPlugin(),
    LexiconPlugin(),
    LivePlugin(),
    RoomPlugin(),
    QdrantPlugin(),
)
