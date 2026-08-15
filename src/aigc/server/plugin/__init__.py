from litestar.plugins import PluginProtocol

from .alchemy import AlchemyPlugin
from .auth import AuthPlugin
from .context import ContextPlugin
from .docs import ScalarRenderPlugin
from .qdrant import QdrantPlugin

__all__ = (
    "AlchemyPlugin",
    "AuthPlugin",
    "ContextPlugin",
    "QdrantPlugin",
    "ScalarRenderPlugin",
)


plugins: tuple[PluginProtocol, ...] = (
    AlchemyPlugin(),
    AuthPlugin(),
    ContextPlugin(),
    QdrantPlugin(),
)
