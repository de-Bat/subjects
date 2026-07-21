import pytest

from app.models.schemas import PrimarySubject, Signals, VisionResult
from app.resolvers.movie import MovieResolver


@pytest.mark.asyncio
async def test_enrich_without_api_key_keeps_subject(monkeypatch):
    from app.resolvers import movie as mod

    class FakeSettings:
        tmdb_api_key = None
    monkeypatch.setattr(mod, "get_settings", lambda: FakeSettings())

    vision = VisionResult(
        primary_subject=PrimarySubject(subject_type="show", title="Priscilla",
                                       why="Apple TV+ series"),
        title_guess="Priscilla",
    )
    sig = Signals(input_type="image", vision=vision)
    item = await MovieResolver().enrich(sig)

    assert item.title == "Priscilla"
    assert item.attributes.get("_enrich_incomplete") == "No TMDb API key configured"
    assert item.confidence <= 0.3
