"""Live comment window state handlers."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from echocue.core.lexicon import (
    FakeSemanticClassificationClient,
    SemanticClassificationClient,
    SemanticClassificationCommentStruct,
    SemanticClassificationRequestStruct,
)
from echocue.core.lexicon.classification import DEFAULT_SEMANTIC_CLASSIFICATION_TOP_N
from echocue.core.live.schema import LiveCommentEventStruct

from .schema import CommentWindowCandidateStruct, CommentWindowItemStruct, CommentWindowStruct

__all__ = ("CommentWindowHandler",)


class CommentWindowHandler:
    """Maintain in-memory comment windows for livestream rooms."""

    def __init__(
        self,
        window_duration: timedelta = timedelta(seconds=10),
        classification_client: SemanticClassificationClient | None = None,
        top_n: int = DEFAULT_SEMANTIC_CLASSIFICATION_TOP_N,
    ) -> None:
        self._window_duration = window_duration
        self._classification_client = classification_client or FakeSemanticClassificationClient()
        self._top_n = top_n
        self._items_by_room: dict[str, list[CommentWindowItemStruct]] = defaultdict(list)
        self._comment_ids_by_room: dict[str, set[str]] = defaultdict(set)

    async def ingest_comment(self, event: LiveCommentEventStruct) -> CommentWindowStruct:
        """Add a comment event to its room window and return the current snapshot."""

        room_id = event.room_id
        self._prune_room(room_id, event.occurred_at)
        if event.payload.comment_id not in self._comment_ids_by_room[room_id]:
            item = CommentWindowItemStruct(
                comment_id=event.payload.comment_id,
                user_id=event.user_id,
                nickname=event.payload.nickname,
                content=event.payload.content,
                occurred_at=event.occurred_at,
            )
            self._items_by_room[room_id].append(item)
            self._comment_ids_by_room[room_id].add(item.comment_id)

        return await self.get_window(room_id, now=event.occurred_at)

    async def get_window(self, room_id: str, now: datetime | None = None) -> CommentWindowStruct:
        """Return the current comment window snapshot for a room."""

        window_ended_at = now or datetime.now(UTC)
        self._prune_room(room_id, window_ended_at)
        items = list(self._items_by_room[room_id])
        window_started_at = window_ended_at - self._window_duration
        text_batch = [item.content for item in items]
        result = await self._classification_client.classify(
            SemanticClassificationRequestStruct(
                room_id=room_id,
                text_batch=text_batch,
                top_n=self._top_n,
                comment_batch=[
                    SemanticClassificationCommentStruct(comment_id=item.comment_id, text=item.content)
                    for item in items
                ],
            )
        )

        return CommentWindowStruct(
            room_id=room_id,
            window_started_at=window_started_at,
            window_ended_at=window_ended_at,
            total_count=len(items),
            unique_user_count=len({item.user_id for item in items}),
            comments=items,
            text_batch=text_batch,
            semantic_type=result.semantic_type,
            confidence=result.confidence,
            top_n=result.top_n,
            candidates=[
                CommentWindowCandidateStruct(
                    comment_id=candidate.comment_id,
                    text=candidate.text,
                    semantic_type=candidate.semantic_type,
                    score=candidate.score,
                    confidence=candidate.confidence,
                )
                for candidate in result.candidates
            ],
        )

    def _prune_room(self, room_id: str, now: datetime) -> None:
        window_started_at = now - self._window_duration
        items = [item for item in self._items_by_room[room_id] if item.occurred_at >= window_started_at]
        self._items_by_room[room_id] = items
        self._comment_ids_by_room[room_id] = {item.comment_id for item in items}

    async def load_comments(self, events: Iterable[LiveCommentEventStruct]) -> None:
        """Load multiple comment events into their room windows."""

        for event in events:
            await self.ingest_comment(event)
