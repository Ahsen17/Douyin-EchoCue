from echocue.base.schema import BaseStruct

__all__ = ("LiveConfig",)


class LiveConfig(BaseStruct):
    """Configuration for live-domain runtime capabilities."""

    room_status_cache_ttl_seconds: int = 7_200
