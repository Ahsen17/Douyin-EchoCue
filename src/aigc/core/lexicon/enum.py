from enum import StrEnum, auto

__all__ = ("SemanticType",)


class SemanticType(StrEnum):
    """Predefined semantic categories for live interaction value."""

    PLAYFUL_JOKE = auto()
    """Funny, playful, contrasting, or joke-like comments suitable for a quick response."""

    PERSONA_PRAISE = auto()
    """Praise for the host, team, persona, or live performance."""

    INTERACTIVE_PROMPT = auto()
    """Comments that invite the host to respond or naturally extend the conversation."""

    ATMOSPHERE_BOOST = auto()
    """Comments that can lift room energy, continue a room meme, or rally interaction."""

    OTHER = auto()
    """Fallback category used when no reliable semantic category is available."""
