"""Social resolver: twitter/x, mastodon, bluesky posts and profiles."""
import re

from ..models.schemas import EnrichedItem, Signals
from .base import Resolver
from .generic import GenericResolver

SOCIAL_HOSTS = re.compile(
    r"(twitter\.com|x\.com|mastodon\.\w+|bsky\.app|threads\.net|linkedin\.com|"
    r"instagram\.com|tiktok\.com)", re.I
)


class SocialResolver(Resolver):
    id = "social"
    item_type = "social"
    category_hints = ["Social", "Links"]

    def detect(self, signals: Signals) -> float:
        for candidate in (signals.canonical_url, signals.url,
                          signals.vision.visible_url if signals.vision else None):
            if candidate and SOCIAL_HOSTS.search(candidate):
                return 0.85
        if signals.vision and signals.vision.detected_service in ("twitter", "instagram", "tiktok"):
            return 0.7
        return 0.0

    async def enrich(self, signals: Signals) -> EnrichedItem:
        base = await GenericResolver().enrich(signals)
        base.type = "social"
        host = None
        url = signals.canonical_url or signals.url or ""
        if m := SOCIAL_HOSTS.search(url):
            host = m.group(1).lower()
        base.attributes = {"platform": host}
        base.tags = ["social"] + ([host.split(".")[0]] if host else [])
        base.category_hints = self.category_hints
        base.confidence = min(0.9, base.confidence + 0.1)
        return base
