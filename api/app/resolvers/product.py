"""Product resolver: schema.org Product JSON-LD / og:type=product pages."""
from ..models.schemas import EnrichedItem, Signals
from .article import jsonld_of_type
from .base import Resolver
from .generic import GenericResolver


class ProductResolver(Resolver):
    id = "product"
    item_type = "product"
    category_hints = ["Products"]

    def detect(self, signals: Signals) -> float:
        if jsonld_of_type(signals.jsonld, "Product"):
            return 0.9
        if "product" in signals.og.get("og:type", ""):
            return 0.75
        if signals.vision and signals.vision.detected_service == "product":
            return 0.6
        return 0.0

    async def enrich(self, signals: Signals) -> EnrichedItem:
        base = await GenericResolver().enrich(signals)
        ld = jsonld_of_type(signals.jsonld, "Product") or {}
        offers = ld.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        image = ld.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        if isinstance(image, dict):
            image = image.get("url")
        brand = ld.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        rating = (ld.get("aggregateRating") or {}).get("ratingValue")
        base.type = "product"
        base.title = ld.get("name") or base.title
        base.description = ld.get("description") or base.description
        base.thumbnail_url = image or base.thumbnail_url
        base.attributes = {
            "price": offers.get("price"),
            "currency": offers.get("priceCurrency"),
            "brand": brand,
            "rating": rating,
            "availability": offers.get("availability"),
        }
        base.tags = ["product"] + ([str(brand).lower()] if brand else [])
        base.category_hints = self.category_hints
        base.confidence = 0.9 if ld else min(base.confidence, 0.65)
        return base
