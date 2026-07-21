from app.models.schemas import CandidateEntity, Signals, VisionResult
from app.resolvers.movie import MovieResolver, title_year_from_signals


def _vision(entities, service="instagram", ocr=""):
    return VisionResult(
        detected_service=service,
        ocr_text=ocr,
        candidate_entities=[CandidateEntity(type=t, value=v) for t, v in entities],
    )


def test_detect_media_promo_person_plus_title():
    sig = Signals(input_type="image", vision=_vision(
        [("media_title", "Priscilla"), ("person", "Annette Bening"), ("provider", "Apple TV+")]
    ))
    assert MovieResolver().detect(sig) >= 0.9


def test_detect_media_title_plus_provider_only():
    sig = Signals(input_type="image", vision=_vision(
        [("media_title", "Severance"), ("provider", "Apple TV+")]
    ))
    assert MovieResolver().detect(sig) >= 0.9


def test_detect_ignores_bare_person_without_title():
    sig = Signals(input_type="image", vision=_vision([("person", "Annette Bening")]))
    assert MovieResolver().detect(sig) == 0.0


def test_title_year_reads_media_title_entity():
    sig = Signals(input_type="image", vision=_vision([("media_title", "Priscilla")]))
    title, year = title_year_from_signals(sig)
    assert title == "Priscilla"
