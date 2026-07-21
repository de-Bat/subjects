# Smarter Processing Engine + Provenance + Progress Bar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the pipeline resolve media screenshots (Instagram/Apple TV promos) into rich movie/TV items with cast + streaming provider, record a per-stage "how I got there" provenance trace, and show a stage-segmented progress bar on the item page.

**Architecture:** Backend is a staged async pipeline (`api/app/pipeline/`) feeding pluggable resolvers (`api/app/resolvers/`) that return an `EnrichedItem`; the `movie` resolver is broadened to movies+TV. A `Provenance` accumulator is threaded through the run and persisted into the JSONB `attributes` column (no migration). Frontend (`web/src/`, React + Vite + vitest) consumes existing SSE `stage` events for a progress bar and renders provenance on the item page. Every task extracts a **pure helper** (network/DB/LLM-free) that carries the test, with thin shells wiring it in.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, httpx, Pydantic v2, pytest + pytest-asyncio (`asyncio_mode=auto`); React 18, TypeScript, Vite, vitest (jsdom).

## Global Constraints

- Python `requires-python = ">=3.12"`; no new backend dependencies (httpx, pydantic already present).
- No frontend dependencies added — tests target pure helpers in `web/src/lib/*.test.ts` (no `@testing-library/react`; it is not installed).
- Resolvers must stay drop-in: subclass `Resolver`, keep `id`/`item_type`/`category_hints`, implement `detect()` (sync, network-free) and `async enrich()`. Keep the `movie` resolver's `id = "movie"` (no data migration of existing items).
- LLM calls only via `complete_json(get_provider(), Schema, prompt, system=...)`. Resolvers must never crash the pipeline — the orchestrator already falls back to generic on exceptions.
- Provenance is engine metadata stored under `attributes["_provenance"]`; any attribute key starting with `_` is hidden from the generic attribute table in the UI.
- Backend tests live in `api/tests/`. Run from `api/` with `python -m pytest`. Frontend tests run from `web/` with `npm test`.

---

### Task 1: Schema + vision-prompt additions — provenance types, vision reasoning, media_type

**Files:**
- Modify: `api/app/models/schemas.py`
- Modify: `api/app/ai/prompts.py` (`VISION_SYSTEM`, `TEXT_SIGNALS_SYSTEM`)
- Create: `api/tests/__init__.py` (empty)
- Test: `api/tests/test_schemas.py`

> Note: the `VISION_SYSTEM`/`TEXT_SIGNALS_SYSTEM` prompt edits (Step 3b) are LLM instruction strings with no unit test — the entity types they instruct the model to emit are exercised by the synthetic-entity tests in Task 2 and the manual smoke check. They are grouped here because everything downstream (Task 2 detection, Task 3 enrichment) depends on the VLM emitting `media_title`/`person`/`provider` entities and a `reasoning` field.

**Interfaces:**
- Produces:
  - `VisionResult.reasoning: str = ""`
  - `MoviePick.media_type: Literal["movie", "tv"] | None = None`
  - `class ProvStep(BaseModel)` with fields `stage: str`, `summary: str`, `detail: str | None = None`
  - `class Provenance(BaseModel)` with `steps: list[ProvStep]` and method `add(self, stage: str, summary: str, detail: str | None = None) -> None`

- [ ] **Step 1: Write the failing test**

Create `api/tests/__init__.py` (empty file), then `api/tests/test_schemas.py`:

```python
from app.models.schemas import MoviePick, Provenance, ProvStep, VisionResult


def test_vision_result_reasoning_defaults_empty():
    assert VisionResult().reasoning == ""
    assert VisionResult(reasoning="an Instagram reel").reasoning == "an Instagram reel"


def test_moviepick_media_type_optional():
    assert MoviePick().media_type is None
    assert MoviePick(tmdb_id=1, confidence=0.9, media_type="tv").media_type == "tv"


def test_provenance_add_appends_steps_in_order():
    prov = Provenance()
    prov.add("vision", "Detected instagram")
    prov.add("resolve", "Matched by movie resolver", detail="score=0.90")
    assert [s.stage for s in prov.steps] == ["vision", "resolve"]
    assert prov.steps[1].summary == "Matched by movie resolver"
    assert prov.steps[1].detail == "score=0.90"
    assert prov.steps[0].detail is None


def test_prov_step_is_json_serialisable():
    prov = Provenance()
    prov.add("finalize", "enriched", detail="0.90 >= 0.75")
    dumped = prov.model_dump()["steps"]
    assert dumped == [{"stage": "finalize", "summary": "enriched", "detail": "0.90 >= 0.75"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `api/`): `python -m pytest tests/test_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'Provenance'` (and reasoning/media_type attribute errors).

- [ ] **Step 3: Write minimal implementation**

In `api/app/models/schemas.py`: add `Literal` to the existing typing import line (`from typing import Literal` is already imported — confirm it is; it is used for `InputType`). Then:

Add `reasoning: str = ""` to `VisionResult` (after `ocr_text`):

```python
class VisionResult(BaseModel):
    """Strict-JSON output of the VLM extraction prompt (Appendix B.1)."""
    detected_service: str = "generic"
    visible_url: str | None = None
    title_guess: str | None = None
    ocr_text: str = ""
    reasoning: str = ""
    candidate_entities: list[CandidateEntity] = Field(default_factory=list)
```

Add `media_type` to `MoviePick`:

```python
class MoviePick(BaseModel):
    tmdb_id: int | None = None
    confidence: float = 0.0
    media_type: Literal["movie", "tv"] | None = None
```

Append the provenance contracts at the end of the file:

```python
class ProvStep(BaseModel):
    """One user-facing step in the 'how I got there' trace."""
    stage: str
    summary: str
    detail: str | None = None


class Provenance(BaseModel):
    """Accumulates ProvSteps across a pipeline run; persisted to attributes._provenance."""
    steps: list[ProvStep] = Field(default_factory=list)

    def add(self, stage: str, summary: str, detail: str | None = None) -> None:
        self.steps.append(ProvStep(stage=stage, summary=summary, detail=detail))
```

- [ ] **Step 3b: Update the vision prompts to emit richer entities + reasoning**

In `api/app/ai/prompts.py`, replace `VISION_SYSTEM` so it (a) adds `instagram`/`tiktok` to the service enum, (b) instructs detecting the container service AND subject independently, (c) lists the new entity types, (d) asks for a one-line `reasoning`, and (e) includes an Instagram media-promo example:

```python
VISION_SYSTEM = (
    "You extract structured signals from a shared image (usually a screenshot of a web page "
    "or social post). "
    'Return ONLY minified JSON of the form: '
    '{"detected_service":<enum>,"visible_url":<string|null>,"title_guess":<string|null>,'
    '"ocr_text":<string>,"reasoning":<string>,'
    '"candidate_entities":[{"type":<string>,"value":<string>}]} '
    'detected_service must be one of ["github","imdb","movie","youtube","twitter","instagram",'
    '"tiktok","product","recipe","article","generic"]. '
    "Detect the container service (instagram, tiktok, imdb...) from logos/URL/layout AND the "
    "subject independently: a movie or TV show promo posted on Instagram is still ABOUT that "
    "movie/show. "
    "Entity types you may emit: repo, movie, media_title, person, character, provider, studio, "
    "year, imdb_id, url, product, other. Use 'media_title' for a film/series title, 'person' for "
    "an actor/creator, and 'provider' for a streaming service (e.g. 'Apple TV+', 'Netflix'). "
    "reasoning is one short sentence describing what you see. "
    'If you cannot tell the service, use "generic". Never output prose, markdown, or explanations '
    "outside the JSON.\n\n"
    "Example 1 - the github.com/facebook/react repository page:\n"
    '{"detected_service":"github","visible_url":"github.com/facebook/react",'
    '"title_guess":"facebook/react","ocr_text":"facebook/react  Public  The library for web and '
    'native user interfaces  230k stars","reasoning":"GitHub repo page for facebook/react",'
    '"candidate_entities":[{"type":"repo","value":"facebook/react"}]}\n'
    "Example 2 - the IMDb page for Dune: Part Two:\n"
    '{"detected_service":"imdb","visible_url":"imdb.com/title/tt15239678",'
    '"title_guess":"Dune: Part Two","ocr_text":"Dune: Part Two  2024  PG-13  8.5/10",'
    '"reasoning":"IMDb title page for the film Dune: Part Two",'
    '"candidate_entities":[{"type":"movie","value":"Dune: Part Two"},'
    '{"type":"year","value":"2024"},{"type":"imdb_id","value":"tt15239678"}]}\n'
    "Example 3 - an Instagram reel from Apple TV showing Annette Bening in a series:\n"
    '{"detected_service":"instagram","visible_url":null,"title_guess":"Priscilla",'
    '"ocr_text":"ANNETTE BENING PRISCILLA  Apple TV  Annette Bening is in her villain era",'
    '"reasoning":"Instagram reel promoting the Apple TV+ series Priscilla",'
    '"candidate_entities":[{"type":"media_title","value":"Priscilla"},'
    '{"type":"person","value":"Annette Bening"},{"type":"provider","value":"Apple TV+"}]}'
)
```

Also extend `TEXT_SIGNALS_SYSTEM`: add `instagram`/`tiktok` to its enum list and add `media_title, person, provider, studio, character` to its "Entity types:" line (append them to the existing list), so pasted-text media blurbs classify the same way.

- [ ] **Step 4: Run test to verify it passes**

Run (from `api/`): `python -m pytest tests/test_schemas.py -v`
Expected: PASS (4 passed). (Prompt strings have no unit test; import-time syntax is exercised by the suite.)

- [ ] **Step 5: Commit**

```bash
git add api/app/models/schemas.py api/app/ai/prompts.py api/tests/__init__.py api/tests/test_schemas.py
git commit -m "feat: add provenance schemas, vision reasoning, media_type; richer vision prompt"
```

---

### Task 2: Broaden media detection (movie resolver detects TV/streaming promos)

**Files:**
- Modify: `api/app/resolvers/movie.py:35-63` (`title_year_from_signals`, `MovieResolver.detect`)
- Test: `api/tests/test_media_detect.py`

**Interfaces:**
- Consumes: `Signals`, `VisionResult`, `CandidateEntity` from `app.models.schemas`; `MovieResolver` from `app.resolvers.movie`.
- Produces: `MovieResolver.detect()` returns ≥0.9 when vision has a `media_title` entity together with a `person`/`actor` or `provider` entity. `title_year_from_signals()` also reads `media_title` entities.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_media_detect.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `api/`): `python -m pytest tests/test_media_detect.py -v`
Expected: FAIL — `test_detect_media_promo_person_plus_title` returns 0.0 (media_title/person entities not yet consulted).

- [ ] **Step 3: Write minimal implementation**

In `api/app/resolvers/movie.py`, update `title_year_from_signals` to also read `media_title`:

```python
def title_year_from_signals(signals: Signals) -> tuple[str | None, str | None]:
    title = None
    year = None
    if signals.vision:
        for ent in signals.vision.candidate_entities:
            if ent.type in ("movie", "media_title") and not title:
                title = ent.value
            if ent.type == "year" and not year:
                year = ent.value
        title = title or signals.vision.title_guess
    title = title or signals.og.get("og:title") or signals.title
    return title, year
```

In `MovieResolver.detect`, add the media-promo branch after the `detected_service` check and before the MOVIE_WORDS text check:

```python
    def detect(self, signals: Signals) -> float:
        if imdb_id_from_signals(signals):
            return 0.95
        if signals.vision and signals.vision.detected_service in ("imdb", "movie"):
            return 0.85
        if signals.vision:
            types = {e.type for e in signals.vision.candidate_entities}
            if "media_title" in types and (
                types & {"person", "actor"} or "provider" in types
            ):
                return 0.9
        text = " ".join(filter(None, [signals.text, signals.body_text,
                                      signals.vision.ocr_text if signals.vision else None]))
        if text and len(MOVIE_WORDS.findall(text)) >= 2:
            return 0.6
        return 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `api/`): `python -m pytest tests/test_media_detect.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add api/app/resolvers/movie.py api/tests/test_media_detect.py
git commit -m "feat: detect TV/streaming media promos from vision entities"
```

---

### Task 3: Media item builder — TV + movie normalization, cast, providers, tags

**Files:**
- Modify: `api/app/resolvers/movie.py` (add `_slug`, `build_media_item`; refactor `enrich` to call it and query both endpoints)
- Modify: `api/app/ai/prompts.py` (rename/extend `MOVIE_PICK_SYSTEM` to accept movie+tv candidates)
- Test: `api/tests/test_media_builder.py`

**Interfaces:**
- Consumes: `EnrichedItem` from `app.models.schemas`.
- Produces: `build_media_item(details: dict, media_type: str, pick_confidence: float) -> EnrichedItem` — pure, no network. `media_type` is `"movie"` or `"tv"`. `_slug(name: str) -> str`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_media_builder.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `api/`): `python -m pytest tests/test_media_builder.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_media_item'`.

- [ ] **Step 3: Write minimal implementation**

In `api/app/resolvers/movie.py`, add imports at top if missing (`re` is already imported). Add near the module-level constants:

```python
def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build_media_item(details: dict, media_type: str, pick_confidence: float) -> "EnrichedItem":
    """Pure: turn a TMDb movie|tv detail payload into an EnrichedItem. No network."""
    is_tv = media_type == "tv"
    tmdb_id = details.get("id")
    title = details.get("title") or details.get("name")
    date = details.get("release_date") or details.get("first_air_date") or ""
    year = date[:4] or None
    runtime = details.get("runtime")
    if runtime is None:
        ert = details.get("episode_run_time") or []
        runtime = ert[0] if ert else None

    cast = [c.get("name") for c in (details.get("credits") or {}).get("cast", [])[:8] if c.get("name")]

    us = (((details.get("watch/providers") or {}).get("results") or {}).get("US") or {})
    providers = [p.get("provider_name") for p in (us.get("flatrate") or []) if p.get("provider_name")]
    apple_original = any("apple tv" in p.lower() for p in providers)
    networks = [n.get("name") for n in (details.get("networks") or []) if n.get("name")]

    trailer = next(
        (f"https://www.youtube.com/watch?v={v['key']}"
         for v in (details.get("videos", {}).get("results") or [])
         if v.get("site") == "YouTube" and v.get("type") == "Trailer"),
        None,
    )
    imdb_id = (details.get("external_ids") or {}).get("imdb_id") or details.get("imdb_id")
    poster = details.get("poster_path")
    path = "tv" if is_tv else "movie"

    attributes = {
        "type": "show" if is_tv else "movie",
        "rating": details.get("vote_average"),
        "votes": details.get("vote_count"),
        "runtime": runtime,
        "year": year,
        "tmdb_id": tmdb_id,
        "cast": cast,
        "provider": providers,
        "apple_original": apple_original,
    }
    if is_tv:
        attributes["network"] = networks

    tags = [g["name"].lower() for g in (details.get("genres") or [])]
    tags += [f"actor:{_slug(n)}" for n in cast]
    tags += [f"provider:{_slug(p)}" for p in providers]
    if apple_original:
        tags.append("apple-original")
    if year:
        tags.append(year)

    return EnrichedItem(
        type="show" if is_tv else "movie",
        title=title,
        description=details.get("overview"),
        canonical_url=f"https://www.themoviedb.org/{path}/{tmdb_id}",
        thumbnail_url=f"{IMG}/w500{poster}" if poster else None,
        icon_url=f"{IMG}/w92{poster}" if poster else None,
        attributes=attributes,
        links={
            "trailer": trailer,
            "imdb": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None,
            "homepage": details.get("homepage") or None,
        },
        tags=tags,
        category_hints=["Movies"],
        confidence=min(0.97, max(pick_confidence, 0.5) * 0.97),
    )
```

Now refactor `MovieResolver.enrich` and `_identify` to search both endpoints and delegate to the builder. Replace the body of `enrich` (the part after the api_key guard) and `_identify`:

```python
    async def enrich(self, signals: Signals) -> EnrichedItem:
        api_key = get_settings().tmdb_api_key
        if not api_key:
            return EnrichedItem(type="movie", title=signals.title, confidence=0.2,
                                attributes={"error": "TMDB_API_KEY not configured"})

        async with httpx.AsyncClient(timeout=20.0) as client:
            tmdb_id, media_type, pick_confidence = await self._identify(client, api_key, signals)
            if tmdb_id is None:
                title, _ = title_year_from_signals(signals)
                return EnrichedItem(type="movie", title=title, confidence=min(pick_confidence, 0.4))

            details = (await client.get(
                f"{TMDB}/{media_type}/{tmdb_id}",
                params={"api_key": api_key,
                        "append_to_response": "videos,external_ids,credits,watch/providers"},
            )).json()

        return build_media_item(details, media_type, pick_confidence)

    async def _identify(self, client, api_key, signals):
        """Return (tmdb_id, media_type, confidence)."""
        if imdb_id := imdb_id_from_signals(signals):
            resp = await client.get(
                f"{TMDB}/find/{imdb_id}", params={"api_key": api_key, "external_source": "imdb_id"}
            )
            data = resp.json()
            if data.get("movie_results"):
                return data["movie_results"][0]["id"], "movie", 0.98
            if data.get("tv_results"):
                return data["tv_results"][0]["id"], "tv", 0.98

        title, year = title_year_from_signals(signals)
        if not title:
            return None, "movie", 0.0

        candidates = []
        for media_type in ("movie", "tv"):
            params = {"api_key": api_key, "query": title}
            if year:
                params["year"] = year
            resp = await client.get(f"{TMDB}/search/{media_type}", params=params)
            for c in (resp.json().get("results") or [])[:5]:
                date = c.get("release_date") or c.get("first_air_date") or ""
                candidates.append({
                    "id": c["id"], "media_type": media_type,
                    "title": c.get("title") or c.get("name"),
                    "release_year": int(date[:4]) if date[:4].isdigit() else None,
                })
        if not candidates:
            return None, "movie", 0.0

        payload = {
            "context": {"title_guess": title, "year": year,
                        "ocr_text": (signals.vision.ocr_text[:1000] if signals.vision else None)},
            "candidates": candidates,
        }
        pick = await complete_json(
            get_provider(), MoviePick, json.dumps(payload), system=prompts.MOVIE_PICK_SYSTEM
        )
        if not pick or pick.tmdb_id is None:
            return None, "movie", pick.confidence if pick else 0.0
        media_type = pick.media_type or "movie"
        valid_ids = {c["id"] for c in candidates if c["media_type"] == media_type}
        if pick.tmdb_id not in valid_ids:
            return None, media_type, 0.2
        return pick.tmdb_id, media_type, pick.confidence
```

Update `MOVIE_PICK_SYSTEM` in `api/app/ai/prompts.py` so the model returns `media_type`:

```python
MOVIE_PICK_SYSTEM = (
    "You are matching a shared item to the correct movie OR TV show. You are given extracted "
    "context and a list of TMDb candidates, each tagged with media_type ('movie' or 'tv'). "
    'Return ONLY {"tmdb_id":<int|null>,"media_type":<"movie"|"tv"|null>,"confidence":<0..1>}. '
    "Prefer an exact title + release-year match; a TV show and a movie can share a title, so use "
    "the media_type of the candidate you pick. If no candidate is a confident match, return "
    "null and a low confidence.\n\n"
    'Example input: {"context":{"title_guess":"Priscilla","year":"2026"},'
    '"candidates":[{"id":220000,"media_type":"tv","title":"Priscilla","release_year":2026},'
    '{"id":842675,"media_type":"movie","title":"Priscilla","release_year":2023}]} -> '
    '{"tmdb_id":220000,"media_type":"tv","confidence":0.96}\n'
    'Example input: {"context":{"title_guess":"Dune","year":null},'
    '"candidates":[{"id":438631,"media_type":"movie","title":"Dune","release_year":2021},'
    '{"id":841,"media_type":"movie","title":"Dune","release_year":1984}]} -> '
    '{"tmdb_id":null,"media_type":null,"confidence":0.4}'
)
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `api/`): `python -m pytest tests/test_media_builder.py tests/test_media_detect.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add api/app/resolvers/movie.py api/app/ai/prompts.py api/tests/test_media_builder.py
git commit -m "feat: media resolver resolves TV+movies with cast, providers, actor/provider tags"
```

---

### Task 4: Instagram/TikTok social hosts + media-beats-social registry ordering

**Files:**
- Modify: `api/app/resolvers/social.py:8-25`
- Test: `api/tests/test_resolver_pick.py`

**Interfaces:**
- Consumes: `registry.pick(signals) -> Resolver` from `app.resolvers.registry`; `SocialResolver` from `app.resolvers.social`.
- Produces: `SocialResolver.detect()` scores 0.85 for instagram/tiktok/threads hosts; a media-promo screenshot resolves to the `movie` resolver, a plain social post to `social`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_resolver_pick.py`:

```python
from app.models.schemas import CandidateEntity, Signals, VisionResult
from app.resolvers import registry
from app.resolvers.social import SocialResolver


def test_instagram_host_detected_as_social():
    sig = Signals(input_type="url", canonical_url="https://www.instagram.com/reel/abc/")
    assert SocialResolver().detect(sig) >= 0.85


def test_media_promo_beats_social():
    vision = VisionResult(
        detected_service="instagram",
        candidate_entities=[
            CandidateEntity(type="media_title", value="Priscilla"),
            CandidateEntity(type="person", value="Annette Bening"),
            CandidateEntity(type="provider", value="Apple TV+"),
        ],
    )
    sig = Signals(input_type="image", canonical_url="https://www.instagram.com/reel/abc/", vision=vision)
    assert registry.pick(sig).id == "movie"


def test_plain_social_post_stays_social():
    vision = VisionResult(detected_service="instagram", ocr_text="just a selfie")
    sig = Signals(input_type="image", canonical_url="https://www.instagram.com/p/xyz/", vision=vision)
    assert registry.pick(sig).id == "social"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `api/`): `python -m pytest tests/test_resolver_pick.py -v`
Expected: FAIL — `test_instagram_host_detected_as_social` returns 0.0 (instagram not in `SOCIAL_HOSTS`).

- [ ] **Step 3: Write minimal implementation**

In `api/app/resolvers/social.py`, extend hosts and vision services (leave scores as-is — the media resolver's 0.9 in Task 2 outranks social's 0.85, which is why a promo picks `movie` while a plain post stays `social`):

```python
SOCIAL_HOSTS = re.compile(
    r"(twitter\.com|x\.com|mastodon\.\w+|bsky\.app|threads\.net|linkedin\.com|"
    r"instagram\.com|tiktok\.com)", re.I
)
```

And in `detect`, broaden the vision-service check:

```python
        if signals.vision and signals.vision.detected_service in ("twitter", "instagram", "tiktok"):
            return 0.7
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `api/`): `python -m pytest tests/test_resolver_pick.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add api/app/resolvers/social.py api/tests/test_resolver_pick.py
git commit -m "feat: recognize instagram/tiktok/threads; media promos outrank social"
```

---

### Task 5: GitHub icon guarantee

**Files:**
- Modify: `api/app/resolvers/github.py` (add `github_icon` helper; use it in `enrich`)
- Test: `api/tests/test_github_icon.py`

**Interfaces:**
- Produces: `github_icon(data: dict, owner: str) -> str` — returns the API avatar or `https://github.com/<owner>.png` fallback.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_github_icon.py`:

```python
from app.resolvers.github import github_icon


def test_uses_api_avatar_when_present():
    data = {"owner": {"avatar_url": "https://avatars.githubusercontent.com/u/1?v=4"}}
    assert github_icon(data, "facebook") == "https://avatars.githubusercontent.com/u/1?v=4"


def test_falls_back_to_owner_png_when_missing():
    assert github_icon({}, "facebook") == "https://github.com/facebook.png"
    assert github_icon({"owner": {}}, "vercel") == "https://github.com/vercel.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `api/`): `python -m pytest tests/test_github_icon.py -v`
Expected: FAIL — `ImportError: cannot import name 'github_icon'`.

- [ ] **Step 3: Write minimal implementation**

In `api/app/resolvers/github.py`, add after the regex constants:

```python
def github_icon(data: dict, owner: str) -> str:
    return (data.get("owner") or {}).get("avatar_url") or f"https://github.com/{owner}.png"
```

Then in `enrich`, replace the `icon_url`/`thumbnail_url` lines in the successful `EnrichedItem(...)` return:

```python
            icon_url=github_icon(data, owner),
            thumbnail_url=github_icon(data, owner),
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `api/`): `python -m pytest tests/test_github_icon.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add api/app/resolvers/github.py api/tests/test_github_icon.py
git commit -m "feat: guarantee github repo icon via owner.png fallback"
```

---

### Task 6: Provenance threading + persistence + finer SSE stage emits

**Files:**
- Create: `api/app/pipeline/provenance.py` (pure describe helpers)
- Modify: `api/app/pipeline/enrich.py` (add `persist_provenance`)
- Modify: `api/app/pipeline/run.py` (build `Provenance`, append steps, persist, emit `classify`/`resolve`)
- Test: `api/tests/test_provenance_describe.py`

**Interfaces:**
- Consumes: `Signals`, `EnrichedItem`, `Provenance` from `app.models.schemas`.
- Produces (pure, in `provenance.py`):
  - `describe_vision(signals: Signals) -> tuple[str, str | None]` → (summary, detail)
  - `describe_resolve(resolver_id: str, score: float) -> tuple[str, str]`
  - `describe_enrich(enriched: EnrichedItem) -> tuple[str, str | None]`
  - `describe_why(enriched: EnrichedItem) -> str`
  - `describe_finalize(status: str, confidence: float, threshold: float) -> tuple[str, str]`
- Produces (in `enrich.py`): `async persist_provenance(session, item_id: str, prov: Provenance) -> None`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_provenance_describe.py`:

```python
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


def test_describe_resolve_formats_score():
    summary, detail = describe_resolve("movie", 0.9)
    assert "movie" in summary
    assert detail == "score=0.90"


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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `api/`): `python -m pytest tests/test_provenance_describe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.provenance'`.

- [ ] **Step 3: Write minimal implementation**

Create `api/app/pipeline/provenance.py`:

```python
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
```

In `api/app/pipeline/enrich.py`, add:

```python
async def persist_provenance(session, item_id: str, prov) -> None:
    await session.execute(
        text(
            "UPDATE items SET attributes = attributes || "
            "jsonb_build_object('_provenance', CAST(:p AS jsonb)), updated_at=now() WHERE id=:id"
        ),
        {"p": _json(prov.model_dump()["steps"]), "id": item_id},
    )
```

In `api/app/pipeline/run.py`, wire provenance through. Add imports:

```python
from ..models.schemas import Provenance
from . import provenance as prov_desc
```

Then, inside `run_pipeline`, create `prov = Provenance()` right after loading `source`, and append/emit as follows (full stage-by-stage edit):

```python
    prov = Provenance()
    try:
        # 1-2. classify + extract
        signals = await extract(source)
        s, d = prov_desc.describe_vision(signals)
        prov.add("vision", s, d)
        prov.add("classify", f"Classified input as {signals.input_type}")
        async with factory() as session:
            await _emit(session, item_id, "classify")
            await _emit(session, item_id, "extract")
            await session.commit()

        # 3-4. resolve + enrich
        from ..resolvers import registry
        resolver = registry.pick(signals)
        score = 0.0
        try:
            score = resolver.detect(signals)
        except Exception:
            pass
        rs, rd = prov_desc.describe_resolve(resolver.id, score)
        prov.add("resolve", rs, rd)
        async with factory() as session:
            await _emit(session, item_id, "resolve")
            await session.commit()

        resolver_id, enriched = await resolve_and_enrich(signals)
        es, ed = prov_desc.describe_enrich(enriched)
        prov.add("enrich", es, ed)
        prov.add("why", prov_desc.describe_why(enriched))
        async with factory() as session:
            await persist.apply_enriched(session, item_id, resolver_id, enriched)
            await _emit(session, item_id, "enrich", "enriched")
            await session.commit()
```

Keep the existing categorize block, then add a categorize provenance step after it:

```python
            await _emit(session, item_id, "categorize")
            prov.add("categorize", "Filed into: " + (", ".join(cat.categories) or "Inbox"))
            await session.commit()
```

In the dedup duplicate branch, before `return`, add the step and persist:

```python
                prov.add("dedup", "Duplicate of an existing item", detail=str(duplicate_of))
                await _emit(session, item_id, "dedup", "duplicate")
                await persist.persist_provenance(session, item_id, prov)
                await session.commit()
```

In the finalize block, add the finalize step and persist provenance:

```python
        fs, fd = prov_desc.describe_finalize(final_status, enriched.confidence or 0.0, threshold)
        prov.add("finalize", fs, fd)
        async with factory() as session:
            await session.execute(
                text("UPDATE items SET status=:s, updated_at=now() WHERE id=:id"),
                {"s": final_status, "id": item_id},
            )
            await persist.persist_provenance(session, item_id, prov)
            await _emit(session, item_id, "finalize", final_status)
            await session.commit()
```

In the `except Exception` handler, append an error step and persist it after the status UPDATE (before the error emit):

```python
            prov.add("error", "Pipeline failed", detail=str(exc)[:200])
            await persist.persist_provenance(session, item_id, prov)
            await _emit(session, item_id, "error", "failed")
```

(Note: `resolve_and_enrich` still performs the authoritative pick; the extra `registry.pick` above is only to record the detect score for provenance and is cheap/pure.)

- [ ] **Step 4: Run test to verify it passes**

Run (from `api/`): `python -m pytest tests/test_provenance_describe.py -v`
Expected: PASS (6 passed). Then run the whole backend suite to catch import/wiring regressions: `python -m pytest -q` — Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/pipeline/provenance.py api/app/pipeline/enrich.py api/app/pipeline/run.py api/tests/test_provenance_describe.py
git commit -m "feat: record and persist per-stage provenance; emit classify/resolve stages"
```

---

### Task 7: Frontend progress helper + ProcessingProgress component

**Files:**
- Create: `web/src/lib/progress.ts`
- Create: `web/src/lib/progress.test.ts`
- Create: `web/src/components/ProcessingProgress.tsx`
- Modify: `web/src/pages/Item.tsx` (track SSE `stage`, mount the bar)

**Interfaces:**
- Produces (in `progress.ts`):
  - `export const STAGES: string[]` = `["classify","extract","resolve","enrich","categorize","dedup","finalize"]`
  - `export function stageIndex(stage?: string): number` (−1 if unknown)
  - `export function progressState(status: string, stage?: string): { visible: boolean; filledUpTo: number; error: boolean; done: boolean }`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/progress.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { STAGES, progressState, stageIndex } from "./progress";

describe("progress helpers", () => {
  it("maps stages to indices", () => {
    expect(stageIndex("classify")).toBe(0);
    expect(stageIndex("finalize")).toBe(STAGES.length - 1);
    expect(stageIndex("nope")).toBe(-1);
    expect(stageIndex(undefined)).toBe(-1);
  });

  it("is visible and mid-fill while processing", () => {
    const s = progressState("processing", "resolve");
    expect(s.visible).toBe(true);
    expect(s.filledUpTo).toBe(stageIndex("resolve"));
    expect(s.error).toBe(false);
    expect(s.done).toBe(false);
  });

  it("pending with no stage is visible at start", () => {
    const s = progressState("pending", undefined);
    expect(s.visible).toBe(true);
    expect(s.filledUpTo).toBe(-1);
  });

  it("terminal enriched status is done and fully filled, not visible", () => {
    const s = progressState("enriched", "finalize");
    expect(s.visible).toBe(false);
    expect(s.done).toBe(true);
    expect(s.filledUpTo).toBe(STAGES.length - 1);
  });

  it("error status flags error", () => {
    const s = progressState("error", "enrich");
    expect(s.error).toBe(true);
    expect(s.visible).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm test -- progress`
Expected: FAIL — cannot resolve `./progress`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/lib/progress.ts`:

```ts
export const STAGES = [
  "classify", "extract", "resolve", "enrich", "categorize", "dedup", "finalize",
];

const TERMINAL = new Set(["enriched", "needs_review", "duplicate", "rejected", "error", "failed"]);
const ERROR = new Set(["error", "failed"]);

export function stageIndex(stage?: string): number {
  return stage ? STAGES.indexOf(stage) : -1;
}

export function progressState(status: string, stage?: string) {
  const terminal = TERMINAL.has(status);
  const error = ERROR.has(status);
  return {
    visible: !terminal,
    filledUpTo: terminal && !error ? STAGES.length - 1 : stageIndex(stage),
    error,
    done: terminal && !error,
  };
}
```

Create `web/src/components/ProcessingProgress.tsx`:

```tsx
import { STAGES, progressState } from "../lib/progress";

export default function ProcessingProgress({ status, stage }: { status: string; stage?: string }) {
  const { visible, filledUpTo, error } = progressState(status, stage);
  if (!visible) return null;
  return (
    <div className="mb-4">
      <div className="mb-1 flex gap-1">
        {STAGES.map((s, i) => {
          const filled = i <= filledUpTo;
          const current = i === filledUpTo + 1;
          return (
            <div
              key={s}
              title={s}
              className={
                "h-1.5 flex-1 rounded-full transition-colors " +
                (error && filled ? "bg-red-500" : filled ? "bg-indigo-500" : "bg-slate-800") +
                (current ? " animate-pulse bg-indigo-700" : "")
              }
            />
          );
        })}
      </div>
      <p className="text-xs text-slate-500">
        Processing… {stage ? `(${stage})` : ""}
      </p>
    </div>
  );
}
```

Wire into `web/src/pages/Item.tsx`: add a `stage` state, capture it from SSE, and mount the bar. Add the import and state:

```tsx
import ProcessingProgress from "../components/ProcessingProgress";
```

```tsx
  const [stage, setStage] = useState<string | undefined>(undefined);
```

Update the SSE handler in the existing `useEffect`:

```tsx
    return subscribeEvents((ev) => {
      if (ev.item_id === id) {
        if (ev.stage) setStage(ev.stage);
        load();
      }
    });
```

Mount the bar directly above the header `<div className="mb-3 flex items-center gap-2">`:

```tsx
      <ProcessingProgress status={item.status} stage={stage} />
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm test -- progress`
Expected: PASS. Then `npx tsc -b --noEmit` from `web/` — Expected: no type errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/progress.ts web/src/lib/progress.test.ts web/src/components/ProcessingProgress.tsx web/src/pages/Item.tsx
git commit -m "feat: stage-segmented processing progress bar on item page"
```

---

### Task 8: Frontend provenance render + hide engine attributes

**Files:**
- Create: `web/src/lib/provenance.ts`
- Create: `web/src/lib/provenance.test.ts`
- Create: `web/src/components/Provenance.tsx`
- Modify: `web/src/pages/Item.tsx` (use `visibleAttrs`, mount `<Provenance>`)

**Interfaces:**
- Produces (in `provenance.ts`):
  - `export interface ProvStep { stage: string; summary: string; detail?: string | null }`
  - `export function readProvenance(attributes: Record<string, unknown>): ProvStep[]`
  - `export function visibleAttrs(attributes: Record<string, unknown>): [string, unknown][]` — drops keys starting with `_`.

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/provenance.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { readProvenance, visibleAttrs } from "./provenance";

describe("provenance helpers", () => {
  it("reads steps from attributes._provenance", () => {
    const steps = readProvenance({
      type: "show",
      _provenance: [
        { stage: "vision", summary: "detected instagram", detail: null },
        { stage: "why", summary: "cast matched" },
      ],
    });
    expect(steps).toHaveLength(2);
    expect(steps[0].stage).toBe("vision");
    expect(steps[1].summary).toBe("cast matched");
  });

  it("returns empty array when no provenance", () => {
    expect(readProvenance({ type: "movie" })).toEqual([]);
    expect(readProvenance({ _provenance: "garbage" } as never)).toEqual([]);
  });

  it("hides underscore-prefixed keys from the attribute table", () => {
    const attrs = visibleAttrs({ type: "show", cast: ["A"], _provenance: [1], _internal: 2 });
    const keys = attrs.map(([k]) => k);
    expect(keys).toContain("type");
    expect(keys).toContain("cast");
    expect(keys).not.toContain("_provenance");
    expect(keys).not.toContain("_internal");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm test -- provenance`
Expected: FAIL — cannot resolve `./provenance`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/lib/provenance.ts`:

```ts
export interface ProvStep {
  stage: string;
  summary: string;
  detail?: string | null;
}

export function readProvenance(attributes: Record<string, unknown>): ProvStep[] {
  const raw = attributes?._provenance;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (s): s is ProvStep =>
      !!s && typeof s === "object" && typeof (s as ProvStep).stage === "string",
  );
}

export function visibleAttrs(attributes: Record<string, unknown>): [string, unknown][] {
  return Object.entries(attributes || {}).filter(([k]) => !k.startsWith("_"));
}
```

Create `web/src/components/Provenance.tsx`:

```tsx
import { ProvStep } from "../lib/provenance";

export default function Provenance({ steps }: { steps: ProvStep[] }) {
  if (steps.length === 0) return null;
  return (
    <details className="mt-4 rounded-lg border border-slate-800 bg-slate-900/50 p-3">
      <summary className="cursor-pointer text-sm font-medium text-slate-300">
        How I got there
      </summary>
      <ol className="mt-2 space-y-2 text-sm">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-2">
            <span className="mt-0.5 text-xs text-slate-600">{i + 1}</span>
            <div className="min-w-0">
              <span className="mr-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                {s.stage}
              </span>
              <span className="text-slate-300">{s.summary}</span>
              {s.detail && <div className="text-xs text-slate-500">{s.detail}</div>}
            </div>
          </li>
        ))}
      </ol>
    </details>
  );
}
```

Wire into `web/src/pages/Item.tsx`. Add imports:

```tsx
import Provenance from "../components/Provenance";
import { readProvenance, visibleAttrs } from "../lib/provenance";
```

Replace the attribute-entries line:

```tsx
  const attrs = visibleAttrs(item.attributes || {});
```

Mount `<Provenance>` after the attributes `<dl>` block (before the Links block):

```tsx
      <Provenance steps={readProvenance(item.attributes || {})} />
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm test -- provenance`
Expected: PASS. Then from `web/`: `npm test` (full suite) and `npx tsc -b --noEmit` — Expected: all pass, no type errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/provenance.ts web/src/lib/provenance.test.ts web/src/components/Provenance.tsx web/src/pages/Item.tsx
git commit -m "feat: render 'How I got there' provenance; hide engine attributes"
```

---

## Final verification (after all tasks)

- [ ] Backend: from `api/`, `python -m pytest -q` → all pass.
- [ ] Frontend: from `web/`, `npm test` → all pass; `npx tsc -b --noEmit` → clean; `npm run build` → succeeds.
- [ ] Manual smoke (optional, needs stack up via `docker-compose`): share the Bening Instagram screenshot → item resolves to a **show** titled *Priscilla*, attributes show `cast` incl. Annette Bening and `provider` Apple TV+, tags include `actor:annette-bening` + `provider:apple-tv`, the item page shows a progress bar during processing and a "How I got there" section after, and searching "annette bening apple" returns it.
