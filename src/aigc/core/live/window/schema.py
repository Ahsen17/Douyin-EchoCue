"""Comment window schemas and workflow input boundaries."""

from datetime import datetime

from msgspec import field

from aigc.base import BaseStruct, CamelizedBaseStruct
from aigc.core.lexicon import SemanticType
from aigc.core.live._conversion import convert_struct

__all__ = (
    "CommentWindowCandidateStruct",
    "CommentWindowCandidateVO",
    "CommentWindowItemStruct",
    "CommentWindowItemVO",
    "CommentWindowStruct",
    "CommentWindowVO",
    "CommentWindowWorkflowInputStruct",
    "CommentWindowWorkflowInputVO",
)


class CommentWindowItemStruct(BaseStruct):
    """Single normalized comment inside a window snapshot."""

    comment_id: str
    user_id: str
    nickname: str
    content: str
    occurred_at: datetime


class CommentWindowItemVO(CamelizedBaseStruct):
    """Comment item view object returned by API endpoints."""

    comment_id: str
    user_id: str
    nickname: str
    content: str
    occurred_at: datetime

    @classmethod
    def from_struct(cls, data: CommentWindowItemStruct) -> "CommentWindowItemVO":
        """Build a view object from a service-layer comment item."""

        return convert_struct(data, cls)


class CommentWindowCandidateStruct(BaseStruct):
    """Candidate comment selected by semantic classification."""

    comment_id: str
    text: str
    semantic_type: SemanticType
    score: float
    confidence: float


class CommentWindowCandidateVO(CamelizedBaseStruct):
    """Candidate comment view object returned by API endpoints."""

    comment_id: str
    text: str
    semantic_type: SemanticType
    score: float
    confidence: float

    @classmethod
    def from_struct(cls, data: CommentWindowCandidateStruct) -> "CommentWindowCandidateVO":
        """Build a view object from a service-layer candidate."""

        return convert_struct(data, cls)


class CommentWindowStruct(BaseStruct):
    """Service-layer comment window snapshot."""

    room_id: str
    window_started_at: datetime
    window_ended_at: datetime
    total_count: int
    unique_user_count: int
    comments: list[CommentWindowItemStruct]
    text_batch: list[str]
    semantic_type: SemanticType = SemanticType.OTHER
    confidence: float = 0
    top_n: int = 5
    candidates: list[CommentWindowCandidateStruct] = field(default_factory=list)


class CommentWindowVO(CamelizedBaseStruct):
    """Comment window view object returned by API endpoints."""

    room_id: str
    window_started_at: datetime
    window_ended_at: datetime
    total_count: int
    unique_user_count: int
    comments: list[CommentWindowItemVO]
    text_batch: list[str]
    semantic_type: SemanticType
    confidence: float
    top_n: int
    candidates: list[CommentWindowCandidateVO]

    @classmethod
    def from_struct(cls, data: CommentWindowStruct) -> "CommentWindowVO":
        """Build a view object from a service-layer window snapshot."""

        return convert_struct(data, cls)


class CommentWindowWorkflowInputStruct(BaseStruct):
    """Workflow input boundary derived from a comment window.

    Persona profile identity and version are intentionally not part of this
    boundary. The workflow reads and freezes them when it starts.
    """

    room_id: str
    window_started_at: datetime
    window_ended_at: datetime
    total_count: int
    unique_user_count: int
    comments: list[CommentWindowItemStruct]
    text_batch: list[str]
    semantic_type: SemanticType
    confidence: float
    top_n: int
    candidates: list[CommentWindowCandidateStruct]

    @classmethod
    def from_window(cls, data: CommentWindowStruct) -> "CommentWindowWorkflowInputStruct":
        """Build the workflow input from a comment window snapshot."""

        return convert_struct(data, cls)


class CommentWindowWorkflowInputVO(CamelizedBaseStruct):
    """API-facing comment window workflow input view object."""

    room_id: str
    window_started_at: datetime
    window_ended_at: datetime
    total_count: int
    unique_user_count: int
    comments: list[CommentWindowItemVO]
    text_batch: list[str]
    semantic_type: SemanticType
    confidence: float
    top_n: int
    candidates: list[CommentWindowCandidateVO]

    @classmethod
    def from_struct(cls, data: CommentWindowWorkflowInputStruct) -> "CommentWindowWorkflowInputVO":
        """Build a view object from a workflow input boundary."""

        return convert_struct(data, cls)
