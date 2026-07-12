"""Build the {item, tree} payload for the categorization prompt (Appendix B.4)."""
from ..models.schemas import EnrichedItem


def build_payload(enriched: EnrichedItem, tree: list[str]) -> dict:
    return {
        "item": {
            "type": enriched.type,
            "title": enriched.title,
            "description": (enriched.description or "")[:600],
            "attributes": enriched.attributes,
        },
        "tree": tree,
    }
