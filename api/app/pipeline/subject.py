"""Helpers for the comprehension layer: the primary subject and its entities."""
from ..models.schemas import CandidateEntity, VisionResult


def subject_entities(vision: VisionResult | None) -> list[CandidateEntity]:
    """Entities that describe the real subject, dropping collateral (ads, chrome, noise)."""
    if not vision:
        return []
    return [e for e in vision.candidate_entities if e.role == "subject"]
