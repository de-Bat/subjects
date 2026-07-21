from app.models.schemas import EnrichedItem, Signals, VisionResult
from app.pipeline.provenance import (
    describe_enrich, describe_finalize, describe_resolve, describe_vision, describe_why,
)


def test_describe_vision_uses_service_and_reasoning():
    sig = Signals(input_type="image", vision=VisionResult(
        detected_service="instagram", reasoning="Instagram reel promoting a show"))
    summary, detail = describe_vision(sig)
    assert "instagram" in summary.lower()
    assert detail == "Instagram reel promoting a show"


def test_describe_vision_falls_back_to_ocr_snippet():
    sig = Signals(input_type="image", vision=VisionResult(
        detected_service="generic", ocr_text="ANNETTE BENING PRISCILLA APPLE TV"))
    _, detail = describe_vision(sig)
    assert "ANNETTE BENING" in detail


def test_describe_resolve_plain_language_with_subject():
    summary, detail = describe_resolve("movie", 0.9, subject_type="show")
    assert "TV show" in summary
    assert detail == "score=0.90"


def test_describe_resolve_film_phrasing():
    summary, _ = describe_resolve("movie", 0.9, subject_type="movie")
    assert "film" in summary.lower()


def test_describe_vision_narrates_primary_subject():
    from app.models.schemas import PrimarySubject
    sig = Signals(input_type="image", vision=VisionResult(
        detected_service="instagram",
        primary_subject=PrimarySubject(subject_type="show", title="Priscilla")))
    summary, _ = describe_vision(sig)
    assert "Priscilla" in summary


def test_describe_enrich_shows_title_and_type():
    item = EnrichedItem(type="show", title="Priscilla",
                        attributes={"provider": ["Apple TV+"], "cast": ["Annette Bening"]})
    summary, detail = describe_enrich(item)
    assert "Priscilla" in summary and "show" in summary
    assert "Apple TV+" in detail and "Annette Bening" in detail


def test_describe_why_mentions_provider_and_cast():
    item = EnrichedItem(type="show", title="Priscilla",
                        attributes={"provider": ["Apple TV+"], "cast": ["Annette Bening"]})
    assert "Apple TV+" in describe_why(item)


def test_describe_finalize():
    summary, detail = describe_finalize("enriched", 0.9, 0.75)
    assert summary == "enriched"
    assert detail == "confidence 0.90 >= threshold 0.75"
