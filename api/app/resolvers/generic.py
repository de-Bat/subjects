"""Fallback resolver: build the best possible item from raw signals, flagged lower-confidence."""
from ..models.schemas import EnrichedItem, Signals
from .base import Resolver


def og_get(og: dict, *keys: str) -> str | None:
    for k in keys:
        if og.get(k):
            return og[k]
    return None


class GenericResolver(Resolver):
    id = "generic"
    item_type = "generic"
    category_hints = ["Inbox"]

    def detect(self, signals: Signals) -> float:
        return 0.1  # always applicable, never wins against a confident typed resolver

    async def enrich(self, signals: Signals) -> EnrichedItem:
        og = signals.og
        vision = signals.vision

        title = (
            og_get(og, "og:title", "twitter:title", "page_title")
            or (vision.title_guess if vision else None)
            or signals.title
        )
        description = (
            og_get(og, "og:description", "twitter:description", "description")
            or (signals.body_text[:400] if signals.body_text else None)
            or (signals.text[:400] if signals.text else None)
            or ((vision.ocr_text[:400] or None) if vision else None)
        )
        thumbnail = og_get(og, "og:image", "twitter:image")
        icon = og.get("icon")

        item_type = "generic"
        if og.get("og:type", "").startswith("article") or (vision and vision.detected_service == "article"):
            item_type = "article"

        # Lower-confidence by design: rich OG data caps at 0.85, bare guesses land in review.
        confidence = 0.4
        if title:
            confidence += 0.2
        if description:
            confidence += 0.15
        if thumbnail:
            confidence += 0.1
        confidence = min(confidence, 0.85)
        if signals.input_type != "url" and not (vision and vision.ocr_text):
            confidence = min(confidence, 0.5)

        return EnrichedItem(
            type=item_type,
            title=title,
            description=description,
            canonical_url=signals.canonical_url or signals.url,
            icon_url=icon,
            thumbnail_url=thumbnail,
            links={"source": signals.canonical_url or signals.url} if (signals.canonical_url or signals.url) else {},
            confidence=confidence,
            category_hints=["Links"] if signals.url else ["Inbox"],
        )
