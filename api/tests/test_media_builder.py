from app.resolvers.movie import _slug, build_media_item

TV_DETAILS = {
    "id": 220000,
    "name": "Priscilla",
    "overview": "A drama series.",
    "first_air_date": "2026-01-15",
    "poster_path": "/poster.jpg",
    "episode_run_time": [52],
    "vote_average": 7.8,
    "vote_count": 120,
    "genres": [{"name": "Drama"}],
    "networks": [{"name": "Apple TV+"}],
    "external_ids": {"imdb_id": "tt9999999"},
    "credits": {"cast": [
        {"name": "Annette Bening"}, {"name": "Someone Else"},
    ]},
    "watch/providers": {"results": {"US": {"flatrate": [{"provider_name": "Apple TV+"}]}}},
    "videos": {"results": [{"site": "YouTube", "type": "Trailer", "key": "abc123"}]},
}


def test_slug():
    assert _slug("Annette Bening") == "annette-bening"
    assert _slug("Apple TV+") == "apple-tv"


def test_build_tv_item_core_fields():
    item = build_media_item(TV_DETAILS, "tv", 0.9)
    assert item.type == "show"
    assert item.title == "Priscilla"
    assert item.description == "A drama series."
    assert item.canonical_url == "https://www.themoviedb.org/tv/220000"
    assert item.attributes["type"] == "show"
    assert item.attributes["year"] == "2026"
    assert item.attributes["runtime"] == 52
    assert item.attributes["network"] == ["Apple TV+"]


def test_build_tv_item_cast_and_providers():
    item = build_media_item(TV_DETAILS, "tv", 0.9)
    assert item.attributes["cast"] == ["Annette Bening", "Someone Else"]
    assert item.attributes["provider"] == ["Apple TV+"]
    assert item.attributes["apple_original"] is True


def test_build_tv_item_tags_enable_search():
    item = build_media_item(TV_DETAILS, "tv", 0.9)
    assert "actor:annette-bening" in item.tags
    assert "provider:apple-tv" in item.tags
    assert "apple-original" in item.tags
    assert "drama" in item.tags
    assert "2026" in item.tags


def test_build_movie_item_uses_movie_keys_and_path():
    details = {
        "id": 693134, "title": "Dune: Part Two", "overview": "o",
        "release_date": "2024-03-01", "runtime": 166, "poster_path": "/p.jpg",
        "genres": [{"name": "Sci-Fi"}], "credits": {"cast": []},
        "watch/providers": {"results": {}}, "videos": {"results": []},
        "external_ids": {"imdb_id": "tt15239678"},
    }
    item = build_media_item(details, "movie", 0.98)
    assert item.type == "movie"
    assert item.attributes["type"] == "movie"
    assert item.canonical_url == "https://www.themoviedb.org/movie/693134"
    assert item.attributes.get("apple_original") is False
    assert item.links["imdb"] == "https://www.imdb.com/title/tt15239678/"


def test_tv_show_filed_under_tv_shows():
    details = {"id": 1, "name": "Priscilla", "first_air_date": "2026-01-01",
               "episode_run_time": [42], "overview": "A series."}
    item = build_media_item(details, "tv", 0.9)
    assert item.type == "show"
    assert item.category_hints == ["TV Shows"]


def test_movie_stays_under_movies():
    details = {"id": 2, "title": "Dune", "release_date": "2021-01-01", "overview": "A film."}
    item = build_media_item(details, "movie", 0.9)
    assert item.category_hints == ["Movies"]
