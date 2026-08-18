from typing import Any, cast

from autogen_core.models import ChatCompletionClient
from pydantic import BaseModel

from echocue.base import BaseStruct
from echocue.shared.agentic import ChatAgentLoader
from echocue.shared.encoder import Jinja2Encoder


class AgentResult(BaseModel):
    """Structured output used to verify loader configuration."""

    value: str


def test_loader_passes_structured_output_type_to_autogen(mocker: Any, tmp_path: Any) -> None:
    template = tmp_path / "interest_agent.jinja"
    template.write_text(
        "---\n"
        "name: interest_agent\n"
        "description: Interest selection agent.\n"
        "---\n"
        "Select one candidate.\n",
        encoding="utf-8",
    )
    assistant_agent = mocker.patch("echocue.shared.agentic.loader.AssistantAgent")
    loader: ChatAgentLoader[BaseStruct] = ChatAgentLoader(Jinja2Encoder(tmp_path))

    loader.load_from_template(
        "interest_agent",
        cast("ChatCompletionClient", object()),
        output_content_type=AgentResult,
    )

    assert assistant_agent.call_args.kwargs["output_content_type"] is AgentResult
