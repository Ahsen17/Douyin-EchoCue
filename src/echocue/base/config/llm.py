from typing import Literal

from msgspec import field

from echocue.base.schema import BaseStruct

__all__ = (
    "LLMConfig",
    "LLMProvider",
)


class LLMProvider(BaseStruct):
    """LLM provider configuration."""

    name: str
    base_url: str
    api_key: str
    model_ids: list[str]
    protocol: Literal["openai"] = "openai"


class LLMConfig(BaseStruct):
    """LLM configuration."""

    providers: list[LLMProvider] = field(default_factory=list)

    def provide(self, name: str) -> LLMProvider:
        """Provide a LLM provider by name."""

        if not self.providers:
            raise RuntimeError("No LLM providers configured.")

        provider = next((p for p in self.providers if p.name == name), None)
        if provider is None:
            raise ValueError(f"LLM provider not supported: {name}")

        return provider
