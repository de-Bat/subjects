"""YouTube resolver: video URL / screenshot -> oEmbed-enriched item (no API key needed)."""
import re

import httpx

from ..models.schemas import EnrichedItem, Signals
from .base import Resolver

VIDEO_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]{6,})")


def video_id(signals: Signals) -> str | None:
    for candidate in (signals.canonical_url, signals.url,
                      signals.vision.visible_url if signals.vision else None, signals.text):
        if candidate and (m := VIDEO_RE.search(candidate)):
            return m.group(1)
    return None


class YouTubeResolver(Resolver):
    id = "youtube"
    item_type = "youtube"
    category_hints = ["Links"]

    def detect(self, signals: Signals) -> float:
        if video_id(signals):
            return 0.95
        if signals.vision and signals.vision.detected_service == "youtube":
            return 0.7
        return 0.0

    async def enrich(self, signals: Signals) -> EnrichedItem:
        vid = video_id(signals)
        if not vid:
            return EnrichedItem(type="youtube", title=signals.title, confidence=0.3)
        url = f"https://www.youtube.com/watch?v={vid}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://www.youtube.com/oembed", params={"url": url, "format": "json"}
            )
            data = resp.json() if resp.status_code == 200 else {}
        return EnrichedItem(
            type="youtube",
            title=data.get("title") or signals.og.get("og:title") or signals.title,
            description=signals.og.get("og:description"),
            canonical_url=url,
            thumbnail_url=data.get("thumbnail_url") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            attributes={"channel": data.get("author_name"), "video_id": vid},
            links={"video": url, "channel": data.get("author_url")},
            tags=["video", "youtube"],
            category_hints=self.category_hints,
            confidence=0.95 if data else 0.7,
        )
