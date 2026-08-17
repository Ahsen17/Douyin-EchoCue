from echocue.base.schema import BaseStruct

__all__ = ("EmbeddingConfig",)


class EmbeddingConfig(BaseStruct):
    """Configuration for embedding model."""

    base_url: str = ""
    api_key: str = ""
    model: str = ""

    timeout: int | None = None
    max_retries: int | None = None
    attempts: int | None = None

    def __post_init__(self) -> None:
        """Keep legacy and new retry fields in sync."""

        if self.max_retries is None and self.attempts is not None:
            self.max_retries = self.attempts

        if self.attempts is None and self.max_retries is not None:
            self.attempts = self.max_retries
