from enum import StrEnum

__all__ = ("SemanticType",)


class SemanticType(StrEnum):
    """Predefined semantic categories for live commerce comments."""

    PRICE_PROMOTION = "price_promotion"
    """Price, discount, coupon, final price, and promotion-related comments."""

    SPECIFICATION = "specification"
    """Size, specification, capacity, model, color, and variant-related comments."""

    STOCK = "stock"
    """Inventory, availability, sold-out, replenishment, and scarcity-related comments."""

    LOGISTICS = "logistics"
    """Shipping time, delivery carrier, postage, freight, and arrival-time comments."""

    AFTER_SALE = "after_sale"
    """Return, exchange, warranty, quality issue, and after-sale policy comments."""

    SELLING_POINT = "selling_point"
    """Product effect, material, ingredient, feature, advantage, and value comments."""

    AUDIENCE_SCENARIO = "audience_scenario"
    """Audience, scenario, usage method, and suitability comments."""

    GENERAL_INTERACTION = "general_interaction"
    """General interaction comments without a concrete product-service question."""

    OTHER = "other"
    """Fallback category used when no reliable semantic category is available."""
