from echocue.base.schema import BaseStruct

__all__ = ("RedisConfig",)


class RedisConfig(BaseStruct):
    """Configuration for Redis cache."""

    dsn: str = "redis://localhost:6379/0"
    pool_enabled: bool = False
    pool_size: int = 50
    connection_timeout: int = 10
