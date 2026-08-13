from typing import Any, Self

from msgspec import (
    Struct,
    convert,
    json,
    to_builtins,
    toml,
    yaml,
)
from pydantic import BaseModel

__all__ = (
    "BaseModel",
    "BaseStruct",
    "CamelizedBaseStruct",
)


class BaseStruct(Struct):
    """Base data structure schema."""

    def to_dict(
        self,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = False,
    ) -> dict[str, Any]:
        """Convert the data structure to a dictionary."""

        obj = to_builtins(self)
        attrs = set(obj.keys())

        if include is not None:
            attrs &= include
        if exclude is not None:
            attrs -= exclude
        if exclude_none:
            attrs -= {k for k, v in obj.items() if v is None}

        return {k: obj[k] for k in attrs}

    def to_json(
        self,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = False,
    ) -> str:
        """Convert the data structure to a JSON string."""

        return self.to_jsonb(
            include=include,
            exclude=exclude,
            exclude_none=exclude_none,
        ).decode("utf-8")

    def to_jsonb(
        self,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
        exclude_none: bool = False,
    ) -> bytes:
        """Convert the data structure to a JSONB bytes."""

        return json.encode(
            self.to_dict(
                include=include,
                exclude=exclude,
                exclude_none=exclude_none,
            )
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Convert a dictionary to the data structure."""

        return convert(data, type=cls)

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Convert a JSON string to the data structure."""

        return json.decode(json_str, type=cls)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> Self:
        """Convert a YAML string to the data structure."""

        return yaml.decode(yaml_str, type=cls)

    @classmethod
    def from_toml(cls, toml_str: str) -> Self:
        """Convert a TOML string to the data structure."""

        return toml.decode(toml_str, type=cls)

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """Return the JSON schema of the data structure."""

        return json.schema(type=cls)


class CamelizedBaseStruct(BaseStruct, rename="camel"):
    """Base data structure schema with camel case."""
