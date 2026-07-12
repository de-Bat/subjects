"""Stage 3+4 — pick the winning resolver and run its enrich()."""
from ..models.schemas import EnrichedItem, Signals
from ..resolvers import registry


async def resolve_and_enrich(signals: Signals) -> tuple[str, EnrichedItem]:
    resolver = registry.pick(signals)
    try:
        enriched = await resolver.enrich(signals)
    except Exception:
        # A typed resolver blowing up (network, bad data) must not kill the item.
        # Fall back to generic so the user still gets something usable.
        from ..resolvers.generic import GenericResolver

        resolver = GenericResolver()
        enriched = await resolver.enrich(signals)
        enriched.confidence = min(enriched.confidence, 0.5)
    return resolver.id, enriched
