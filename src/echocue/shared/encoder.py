from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from echocue.base import BaseStruct

__all__ = ("Jinja2Encoder",)


class Jinja2Encoder[T: BaseStruct]:
    """Encoder for Jinja2 templates."""

    def __init__(self, template_path: str | Path) -> None:

        self.env = Environment(
            loader=FileSystemLoader(template_path),
            autoescape=select_autoescape(["jinja"]),
        )

    def render(self, template_name: str, **kwargs: T | Any) -> str:

        return self.env.get_template(
            f"{template_name}.jinja",
        ).render(
            **{
                k: v.to_dict()
                if isinstance(
                    v,
                    BaseStruct,
                )
                else v
                for k, v in kwargs.items()
            }
        )
