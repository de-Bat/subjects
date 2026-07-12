"""Recipe resolver: schema.org Recipe JSON-LD (the standard for recipe sites)."""
from ..models.schemas import EnrichedItem, Signals
from .article import jsonld_of_type
from .base import Resolver
from .generic import GenericResolver


class RecipeResolver(Resolver):
    id = "recipe"
    item_type = "recipe"
    category_hints = ["Recipes"]

    def detect(self, signals: Signals) -> float:
        if jsonld_of_type(signals.jsonld, "Recipe"):
            return 0.95
        if signals.vision and signals.vision.detected_service == "recipe":
            return 0.7
        return 0.0

    async def enrich(self, signals: Signals) -> EnrichedItem:
        base = await GenericResolver().enrich(signals)
        ld = jsonld_of_type(signals.jsonld, "Recipe") or {}
        image = ld.get("image")
        if isinstance(image, dict):
            image = image.get("url")
        if isinstance(image, list):
            image = image[0] if image else None
        ingredients = ld.get("recipeIngredient") or []
        base.type = "recipe"
        base.title = ld.get("name") or base.title
        base.description = ld.get("description") or base.description
        base.thumbnail_url = image or base.thumbnail_url
        base.attributes = {
            "ingredients": ingredients[:50],
            "yield": ld.get("recipeYield"),
            "total_time": ld.get("totalTime"),
            "cuisine": ld.get("recipeCuisine"),
        }
        base.tags = ["recipe"] + ([ld["recipeCuisine"].lower()] if isinstance(ld.get("recipeCuisine"), str) else [])
        base.category_hints = self.category_hints
        base.confidence = 0.95 if ld else min(base.confidence, 0.6)
        return base
