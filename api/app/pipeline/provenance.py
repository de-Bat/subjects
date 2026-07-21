"""Pure helpers that turn pipeline state into user-facing provenance step text."""
from ..models.schemas import EnrichedItem, Signals


def describe_vision(signals: Signals) -> tuple[str, str | None]:
    v = signals.vision
    service = v.detected_service if v else "generic"
    summary = f"Vision: detected {service}"
    detail = None
    if v:
        detail = v.reasoning or (v.ocr_text[:120].strip() or None)
    return summary, detail


def describe_resolve(resolver_id: str, score: float) -> tuple[str, str]:
    return f"Matched by the {resolver_id} resolver", f"score={score:.2f}"


def describe_enrich(enriched: EnrichedItem) -> tuple[str, str | None]:
    summary = f"Enriched as {enriched.type}: {enriched.title or 'Untitled'}"
    bits = []
    if enriched.attributes.get("provider"):
        bits.append("provider " + ", ".join(enriched.attributes["provider"]))
    if enriched.attributes.get("cast"):
        bits.append("cast " + ", ".join(enriched.attributes["cast"][:3]))
    return summary, ("; ".join(bits) or None)


def describe_why(enriched: EnrichedItem) -> str:
    parts = [f"Identified as {enriched.type} '{enriched.title}'"] if enriched.title else []
    if enriched.attributes.get("cast"):
        parts.append("cast matched (" + ", ".join(enriched.attributes["cast"][:2]) + ")")
    if enriched.attributes.get("provider"):
        parts.append("available on " + ", ".join(enriched.attributes["provider"]))
    return "; ".join(parts) or "Best available match for the extracted signals"


def describe_finalize(status: str, confidence: float, threshold: float) -> tuple[str, str]:
    op = ">=" if confidence >= threshold else "<"
    return status, f"confidence {confidence:.2f} {op} threshold {threshold:.2f}"
