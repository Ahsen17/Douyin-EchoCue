"""Client plugin dependency registration tests."""

from collections.abc import Awaitable, Callable
from typing import cast

from litestar import Litestar
from litestar.config.app import AppConfig
from pytest import MonkeyPatch
from redis.asyncio import Redis

from echocue.base import ClientConfig, Config
from echocue.core.client import RemediationHandler
from echocue.server.plugin.client import ClientPlugin


class ClosableRedis:
    closed: bool = False

    def register_script(self, _: str) -> Callable[..., Awaitable[None]]:
        async def script(**__: object) -> None:
            return None

        return script

    async def aclose(self) -> None:
        self.closed = True


class TestClientPlugin:
    async def test_registers_remediation_handler_and_closes_redis(self, monkeypatch: MonkeyPatch) -> None:
        redis = ClosableRedis()
        config = Config(client=ClientConfig(remediation_url="https://webui.example.test/remediation"))
        monkeypatch.setattr(Config, "get", classmethod(lambda cls, filename="config.yaml": config))
        monkeypatch.setattr("echocue.server.plugin.client.Redis.from_url", lambda *args, **kwargs: cast(Redis, redis))

        app_config = ClientPlugin().on_app_init(AppConfig())

        assert isinstance(app_config.state.get("remediation_handler"), RemediationHandler)
        assert app_config.state.get("remediation_redis") is redis
        assert "remediation_handler" in app_config.dependencies
        assert "RemediationHandler" in app_config.signature_namespace

        shutdown_hook = cast("Callable[[Litestar], Awaitable[None]]", app_config.on_shutdown[-1])
        await shutdown_hook(cast(Litestar, None))
        assert redis.closed is True
