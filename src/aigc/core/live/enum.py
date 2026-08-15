"""Live domain enumerations."""

from enum import StrEnum, auto

__all__ = ("SemanticType",)


class SemanticType(StrEnum):
    """Predefined semantic categories for live commerce comments."""

    PRICE_PROMOTION = auto()
    """Comments asking about prices, coupons, discounts, or final payment amounts."""

    SPECIFICATION = auto()
    """Comments asking about size, color, capacity, style, or other product specifications."""

    STOCK = auto()
    """Comments asking about stock, sold-out variants, replenishment, or limited availability."""

    LOGISTICS = auto()
    """Comments asking about shipping time, delivery method, freight, or arrival cycle."""

    AFTER_SALE = auto()
    """Comments asking about returns, exchanges, warranties, quality issues, or after-sale guarantees."""

    SELLING_POINT = auto()
    """Comments asking about product benefits, differentiators, ingredients, materials, or effects."""

    AUDIENCE_SCENARIO = auto()
    """Comments asking whether the product fits a specific user group or usage scenario."""

    GENERAL_INTERACTION = auto()
    """General interaction comments without a concrete product-service question."""

    OTHER = auto()
    """Fallback category used when no reliable semantic category is available."""
