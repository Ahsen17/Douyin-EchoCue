"""Struct conversion helpers for live domain schemas."""

from types import UnionType
from typing import Any, get_args, get_origin

from msgspec import Struct
from msgspec.structs import asdict, fields


def convert_struct[T: Struct](data: Struct, target_type: type[T]) -> T:
    """Convert between Struct types using msgspec field metadata."""

    values = asdict(data)
    converted: dict[str, Any] = {}
    for field in fields(target_type):
        if field.name in values:
            converted[field.name] = _convert_value(values[field.name], field.type)

    return target_type(**converted)


def _convert_value(value: Any, target_type: Any) -> Any:
    if isinstance(target_type, type) and issubclass(target_type, Struct) and isinstance(value, Struct):
        return convert_struct(value, target_type)

    origin = get_origin(target_type)
    if origin is list and isinstance(value, list):
        item_type = get_args(target_type)[0]
        return [_convert_value(item, item_type) for item in value]
    if origin in {UnionType, type(None)}:
        return value

    return value
