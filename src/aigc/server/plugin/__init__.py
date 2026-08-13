from litestar.plugins import InitPluginProtocol

from .alchemy import AlchemyPlugin
from .auth import AuthPlugin
from .context import ContextPlugin
from .docs import ScalarRenderPlugin

__all__ = (
    "AlchemyPlugin",
    "AuthPlugin",
    "ContextPlugin",
    "ScalarRenderPlugin",
)


plugins: tuple[InitPluginProtocol, ...] = (
    AlchemyPlugin(),
    AuthPlugin(),
    ContextPlugin(),
)
