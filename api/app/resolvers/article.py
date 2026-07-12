"""Article resolver: OG/JSON-LD article pages and long-form text."""
from ..models.schemas import EnrichedItem, Signals
from .base import Resolver
from .generic import GenericResolver, og_get


def jsonld_of_type(jsonld: list, *types: str) -> dict | None:
    for block in jsonld:
        t = block.get("@type")
        t_list = t if isinstance(t, list) else [t]
        if any(x in types for x in t_list if x):
            return block
    return None


class ArticleResolver(Resolver):
    id = "article"
    item_type = "article"
    category_hints = ["Articles", "Links"]

    def detect(self, signals: Signals) -> float:
        if jsonld_of_type(signals.jsonld, "Article", "NewsArticle", "BlogPosting"):
            return 0.85
        if signals.og.get("og:type", "").startswith("article"):
            return 0.8
        if signals.vision and signals.vision.detected_service == "article":
            return 0.6
        if signals.input_type == "url" and signals.body_text and len(signals.body_text) > 1500:
            return 0.55
        return 0.0

    async def enrich(self, signals: Signals) -> EnrichedItem:
        base = await GenericResolver().enrich(signals)
        ld = jsonld_of_type(signals.jsonld, "Article", "NewsArticle", "BlogPosting") or {}
        author = ld.get("author")
        if isinstance(author, dict):
            author = author.get("name")
        if isinstance(author, list):
            author = ", ".join(a.get("name", "") if isinstance(a, dict) else str(a) for a in author)
        base.type = "article"
        base.title = ld.get("headline") or base.title
        base.description = base.description or ld.get("description")
        base.attributes = {
            "author": author or og_get(signals.og, "article:author"),
            "published": ld.get("datePublished") or og_get(signals.og, "article:published_time"),
            "site": og_get(signals.og, "og:site_name"),
            "word_count": len(signals.body_text.split()) if signals.body_text else None,
        }
        base.category_hints = self.category_hints
        base.confidence = min(0.9, base.confidence + 0.1)
        return base
