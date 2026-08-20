"""Reusable enum types for external serialization boundaries."""

from enum import StrEnum

__all__ = ("CamelizedStrEnum",)


class CamelizedStrEnum(StrEnum):
    """Generate lower camel case string values from upper snake case members."""

    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list[str]) -> str:
        first, *rest = name.lower().split("_")
        return first + "".join(word.title() for word in rest)
