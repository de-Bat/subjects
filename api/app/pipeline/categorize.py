"""Stage 5 — map enriched item to one-or-more categories + flat tags via the text LLM."""
import json
import logging

from sqlalchemy import text

from ..ai import prompts
from ..ai.provider import complete_json, get_provider
from ..models.schemas import CategorizeResult, EnrichedItem
from .categorize_prompt import build_payload

log = logging.getLogger(__name__)


async def current_tree(session) -> list[str]:
    rows = (await session.execute(text("SELECT name FROM categories ORDER BY name"))).all()
    return [r[0] for r in rows]


async def categorize(session, enriched: EnrichedItem) -> CategorizeResult:
    """Return placements (existing category names) + tags. Falls back to resolver hints."""
    tree = await current_tree(session)
    payload = build_payload(enriched, tree)
    result = await complete_json(
        get_provider(), CategorizeResult, json.dumps(payload), system=prompts.CATEGORIZE_SYSTEM
    )
    valid = set(tree)
    categories: list[str] = []
    tags: list[str] = []
    if result:
        categories = [c for c in result.categories if c in valid]
        tags = [t.strip().lower() for t in result.tags if t.strip()]

    # Merge resolver hints; guarantee at least one placement (Inbox catch-all).
    for hint in enriched.category_hints:
        if hint in valid and hint not in categories:
            categories.append(hint)
    for t in enriched.tags:
        if t and t.lower() not in tags:
            tags.append(t.lower())
    if not categories:
        categories = ["Inbox"] if "Inbox" in valid else (tree[:1] if tree else [])

    # de-dupe tags, keep order
    seen = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))]
    return CategorizeResult(categories=categories, tags=tags[:25])
