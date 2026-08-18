import os
from typing import Any, ClassVar, Self

from msgspec import field

from echocue.base.schema import BaseStruct

from .alchemy import AlchemyConfig
from .app import AppConfig
from .auth import AuthConfig
from .constants import BASE_DIR
from .embedding import EmbeddingConfig
from .lexicon import LexiconConfig
from .llm import LLMConfig
from .logging import LoggingConfig
from .qdrant import QdrantConfig
from .redis import RedisConfig

__all__ = ("Config",)


class Config(BaseStruct):
    """Application core configs."""

    _instance: ClassVar[Self | None] = None

    app: AppConfig = field(default_factory=AppConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)

    redis: RedisConfig = field(default_factory=RedisConfig)
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    alchemy: AlchemyConfig = field(default_factory=AlchemyConfig)

    lexicon: LexiconConfig = field(default_factory=LexiconConfig)

    llm: LLMConfig = field(default_factory=LLMConfig)
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

    if value_type is float:
        try:
            return float(raw_value)
        except ValueError as exc:
            msg = f"Invalid float value for {env_name}: {raw_value!r}"
            raise ValueError(msg) from exc

    return raw_value


_ENV_OVERRIDES: tuple[tuple[str, tuple[str, ...], type[Any]], ...] = (
    ("ECHOCUE_APP_HOST", ("app", "host"), str),
    ("ECHOCUE_APP_PORT", ("app", "port"), int),
    ("ECHOCUE_APP_REQUEST_MAX_BODY_SIZE_MB", ("app", "request_max_body_size_mb"), int),
    ("ECHOCUE_ALCHEMY_URL", ("alchemy", "url"), str),
    ("ECHOCUE_ALCHEMY_ECHO", ("alchemy", "echo"), bool),
    ("ECHOCUE_ALCHEMY_POOL_DISABLED", ("alchemy", "pool_disabled"), bool),
    ("ECHOCUE_REDIS_DSN", ("redis", "dsn"), str),
    ("ECHOCUE_QDRANT_HOST", ("qdrant", "host"), str),
    ("ECHOCUE_QDRANT_PORT", ("qdrant", "port"), int),
    ("ECHOCUE_QDRANT_GRPC_PORT", ("qdrant", "grpc_port"), int),
    ("ECHOCUE_QDRANT_PREFER_GRPC", ("qdrant", "prefer_grpc"), bool),
    ("ECHOCUE_LEXICON_GRPC_ENABLED", ("lexicon", "grpc_enabled"), bool),
    ("ECHOCUE_LEXICON_GRPC_TARGET", ("lexicon", "grpc_target"), str),
    ("ECHOCUE_LEXICON_GRPC_TIMEOUT", ("lexicon", "grpc_timeout"), float),
    ("ECHOCUE_LEXICON_GRPC_HOST", ("lexicon", "grpc_host"), str),
    ("ECHOCUE_LEXICON_GRPC_PORT", ("lexicon", "grpc_port"), int),
    ("ECHOCUE_LEXICON_COLLECTION_NAME", ("lexicon", "collection_name"), str),
    ("ECHOCUE_LOGGING_LEVEL", ("logging", "level"), str),
    ("ECHOCUE_LOGGING_FORMAT", ("logging", "format"), str),
    ("ECHOCUE_LOGGING_FILE_ENABLED", ("logging", "file", "enabled"), bool),
    ("ECHOCUE_LOGGING_FILE_PATH", ("logging", "file", "path"), str),
    ("ECHOCUE_AUTH_SESSION_COOKIE_SECURE", ("auth", "session_cookie_secure"), bool),
)
