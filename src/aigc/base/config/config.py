import os
from typing import Any, ClassVar, Self

from msgspec import field

from aigc.base.schema import BaseStruct

from .alchemy import AlchemyConfig
from .app import AppConfig
from .auth import AuthConfig
from .constants import BASE_DIR
from .embedding import EmbeddingConfig
from .logging import LoggingConfig
from .qdrant import QdrantConfig
from .redis import RedisConfig

__all__ = ("Config",)


class Config(BaseStruct):
    """Application core configs."""

    _instance: ClassVar[Self | None] = None

    app: AppConfig = field(default_factory=AppConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    alchemy: AlchemyConfig = field(default_factory=AlchemyConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)

    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)

    @classmethod
    def get(cls, filename: str = "config.yaml") -> Self:
        if not (confile := BASE_DIR / filename).exists():
            return cls().with_env_overrides()

        if not (configuration := confile.read_text().strip()):
            return cls().with_env_overrides()

        match confile.suffix:
            case ".yaml" | ".yml":
                config = cls.from_yaml(configuration)
            case ".json":
                config = cls.from_json(configuration)
            case ".toml":
                config = cls.from_toml(configuration)
            case _:
                raise ValueError(f"Unsupported config file format: {confile.suffix}")

        return config.with_env_overrides()

    def with_env_overrides(self) -> Self:
        """Return a config object with supported environment variable overrides applied."""

        data = self.to_dict()
        for env_name, path, value_type in _ENV_OVERRIDES:
            raw_value = os.getenv(env_name)
            if raw_value is None:
                continue

            _set_nested_value(data, path, _parse_env_value(env_name, raw_value, value_type))

        return self.from_dict(data)


def _set_nested_value(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    target = data
    for key in path[:-1]:
        nested = target.setdefault(key, {})
        if not isinstance(nested, dict):
            msg = f"Cannot apply config override for {'.'.join(path)}"
            raise TypeError(msg)
        target = nested

    target[path[-1]] = value


def _parse_env_value(env_name: str, raw_value: str, value_type: type[Any]) -> object:
    if value_type is bool:
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False

        msg = f"Invalid boolean value for {env_name}: {raw_value!r}"
        raise ValueError(msg)

    if value_type is int:
        try:
            return int(raw_value)
        except ValueError as exc:
            msg = f"Invalid integer value for {env_name}: {raw_value!r}"
            raise ValueError(msg) from exc

    return raw_value


_ENV_OVERRIDES: tuple[tuple[str, tuple[str, ...], type[Any]], ...] = (
    ("AIGC_APP_HOST", ("app", "host"), str),
    ("AIGC_APP_PORT", ("app", "port"), int),
    ("AIGC_APP_REQUEST_MAX_BODY_SIZE_MB", ("app", "request_max_body_size_mb"), int),
    ("AIGC_ALCHEMY_URL", ("alchemy", "url"), str),
    ("AIGC_ALCHEMY_ECHO", ("alchemy", "echo"), bool),
    ("AIGC_ALCHEMY_POOL_DISABLED", ("alchemy", "pool_disabled"), bool),
    ("AIGC_REDIS_DSN", ("redis", "dsn"), str),
    ("AIGC_QDRANT_HOST", ("qdrant", "host"), str),
    ("AIGC_QDRANT_PORT", ("qdrant", "port"), int),
    ("AIGC_QDRANT_GRPC_PORT", ("qdrant", "grpc_port"), int),
    ("AIGC_QDRANT_PREFER_GRPC", ("qdrant", "prefer_grpc"), bool),
    ("AIGC_LOGGING_LEVEL", ("logging", "level"), str),
    ("AIGC_LOGGING_FORMAT", ("logging", "format"), str),
    ("AIGC_LOGGING_FILE_ENABLED", ("logging", "file", "enabled"), bool),
    ("AIGC_LOGGING_FILE_PATH", ("logging", "file", "path"), str),
    ("AIGC_AUTH_SESSION_COOKIE_SECURE", ("auth", "session_cookie_secure"), bool),
)
