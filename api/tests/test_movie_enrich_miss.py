import pytest

from app.models.schemas import CandidateEntity, PrimarySubject, Signals, VisionResult
from app.resolvers.movie import MovieResolver, imdb_id_from_signals


def test_imdb_id_from_signals_ignores_collateral():
    vision = VisionResult(
        candidate_entities=[
            CandidateEntity(type="imdb_id", value="tt1234567", role="collateral"),
        ],
    )
    sig = Signals(input_type="image", vision=vision)
    assert imdb_id_from_signals(sig) is None


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
    assert item.type == "show"
    assert item.category_hints == ["TV Shows"]


@pytest.mark.asyncio
async def test_enrich_without_api_key_movie_subject(monkeypatch):
    from app.resolvers import movie as mod

    class FakeSettings:
        tmdb_api_key = None
    monkeypatch.setattr(mod, "get_settings", lambda: FakeSettings())

    vision = VisionResult(
        primary_subject=PrimarySubject(subject_type="movie", title="Dune",
                                       why="A film poster"),
        title_guess="Dune",
    )
    sig = Signals(input_type="image", vision=vision)
    item = await MovieResolver().enrich(sig)

    assert item.type == "movie"
    assert item.category_hints == ["Movies"]
