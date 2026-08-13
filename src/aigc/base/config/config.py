from typing import ClassVar, Self

from msgspec import field

from aigc.base.schema import BaseStruct

from .alchemy import AlchemyConfig
from .app import AppConfig
from .auth import AuthConfig
from .constants import BASE_DIR
from .logging import LoggingConfig
from .redis import RedisConfig

__all__ = ("Config",)


class Config(BaseStruct):
    """Application core configs."""

    _instance: ClassVar[Self | None] = None

    app: AppConfig = field(default_factory=AppConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    alchemy: AlchemyConfig = field(default_factory=AlchemyConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)

    @classmethod
    def get(cls, filename: str = "config.yaml") -> Self:
        if not (confile := BASE_DIR / filename).exists():
            return cls()

        if not (configuration := confile.read_text().strip()):
            return cls()

        match confile.suffix:
            case ".yaml" | ".yml":
                return cls.from_yaml(configuration)
            case ".json":
                return cls.from_json(configuration)
            case ".toml":
                return cls.from_toml(configuration)
            case _:
                raise ValueError(f"Unsupported config file format: {confile.suffix}")
