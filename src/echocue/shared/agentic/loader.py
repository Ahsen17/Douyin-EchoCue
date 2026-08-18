from typing import Any

import frontmatter
from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
from pydantic import BaseModel

from echocue.base import BaseStruct, Config
from echocue.shared.encoder import Jinja2Encoder

__all__ = (
    "ChatAgentLoader",
    "ModelClientLoader",
)


class _Frontmatter(BaseStruct):
    """Frontmatter for agentic chat agents."""

    name: str
    description: str

    privoder: str | None = None
    model_id: str | None = None


class ChatAgentLoader[T: BaseStruct]:
    """Agentic chat agent loader based on Jinja2 template."""

    def __init__(self, encoder: Jinja2Encoder) -> None:
        self._encoder = encoder

    def load_from_template(
        self,
        template_name: str,
        model_client: ChatCompletionClient,
        output_content_type: type[BaseModel] | None = None,
        **kwargs: T | Any,
    ) -> AssistantAgent:
        """Load agentic chat agent from template."""

        try:
            post = frontmatter.loads(self._encoder.render(template_name, **kwargs))
            params = _Frontmatter.from_dict(post.metadata)

        except Exception as e:
            raise e from ValueError(f"Invalid frontmatter for template {template_name}: {e}")

        return AssistantAgent(
            name=params.name,
            model_client=model_client,
            description=params.description,
            system_message=post.content,
            output_content_type=output_content_type,
        )


class ModelClientLoader:
    """Model client loader."""

    def load_from_config(self, provider: str, model_id: str) -> OpenAIChatCompletionClient:
        """Load model client from configuration."""

        config = Config.get().llm.provide(provider)
        if model_id not in set(config.model_ids):
            raise ValueError(f"Invalid model ID {model_id} for provider {provider}")

        return OpenAIChatCompletionClient(
            model=model_id,
            base_url=config.base_url,
            api_key=config.api_key,
            organization=config.name,
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": True,
                "family": "unknown",
                "structured_output": True,
                "multiple_system_messages": False,
            }
        )
