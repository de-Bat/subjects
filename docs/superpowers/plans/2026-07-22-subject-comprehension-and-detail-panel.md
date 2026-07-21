# Subject Comprehension + Detail Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the engine understand the real subject of a capture (separating it from collateral noise), file TV shows correctly, gracefully handle enrichment misses, and present the subject as a clean detail card instead of a JSON-like attribute dump.

**Architecture:** Additive changes across the Python pipeline (schemas → prompts → resolve routing → enrich fallback → provenance) and the React detail panel (attrs projection → subject card layout → provenance toggle). All new schema fields are optional/defaulted, so existing items and payloads keep working.

**Tech Stack:** Python 3 + Pydantic v2 + pytest (`api/`), React + TypeScript + Vite + vitest + Tailwind (`web/`).

## Global Constraints

- New `VisionResult` fields MUST be optional with defaults; unknown/legacy payloads keep the current behavior.
- `CandidateEntity.role` defaults to `"subject"`.
- Provenance summaries shown to users are plain-language; raw numbers live only in `ProvStep.detail`.
- Backend tests run with `cd api && pytest`; frontend tests with `cd web && npm test`.
- Conventional Commit messages; commit after each task.

---

### Task 1: Vision schema — PrimarySubject, entity role, subject_entities helper

**Files:**
- Modify: `api/app/models/schemas.py` (CandidateEntity ~line 82, VisionResult ~line 88; add PrimarySubject before VisionResult)
- Create: `api/app/pipeline/subject.py`
- Test: `api/tests/test_subject.py`

**Interfaces:**
- Produces: `PrimarySubject(subject_type: str = "generic", title: str | None, why: str | None)`;
  `CandidateEntity(type, value, role: Literal["subject","collateral"]="subject")`;
  `VisionResult.primary_subject: PrimarySubject | None = None`;
  `subject_entities(vision: VisionResult | None) -> list[CandidateEntity]` (entities with `role == "subject"`; `[]` when vision is None).

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_subject.py
from app.models.schemas import CandidateEntity, PrimarySubject, VisionResult
from app.pipeline.subject import subject_entities


def test_primary_subject_defaults():
    ps = PrimarySubject()
    assert ps.subject_type == "generic" and ps.title is None


def test_entity_role_defaults_to_subject():
    assert CandidateEntity(type="movie", value="Dune").role == "subject"


def test_subject_entities_filters_collateral():
    vision = VisionResult(candidate_entities=[
        CandidateEntity(type="media_title", value="Priscilla", role="subject"),
        CandidateEntity(type="brand", value="SomeAd", role="collateral"),
    ])
    kept = subject_entities(vision)
    assert [e.value for e in kept] == ["Priscilla"]


def test_subject_entities_none_vision():
    assert subject_entities(None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && pytest tests/test_subject.py -v`
Expected: FAIL (`ImportError`: cannot import `PrimarySubject` / `subject_entities`)

- [ ] **Step 3: Write minimal implementation**

In `api/app/models/schemas.py`, replace the `CandidateEntity` class and add `PrimarySubject`, and add the field to `VisionResult`:

```python
class CandidateEntity(BaseModel):
    type: str
    value: str
    role: Literal["subject", "collateral"] = "subject"


class PrimarySubject(BaseModel):
    """The one thing the capture is really about (distinct from the container service)."""
    subject_type: str = "generic"   # show, movie, repo, product, article, paper, recipe, social, youtube, generic
    title: str | None = None
    why: str | None = None
```

In `VisionResult`, add the field right after `detected_service`:

```python
    detected_service: str = "generic"
    primary_subject: PrimarySubject | None = None
```

Create `api/app/pipeline/subject.py`:

```python
"""Helpers for the comprehension layer: the primary subject and its entities."""
from ..models.schemas import CandidateEntity, VisionResult


def subject_entities(vision: VisionResult | None) -> list[CandidateEntity]:
    """Entities that describe the real subject, dropping collateral (ads, chrome, noise)."""
    if not vision:
        return []
    return [e for e in vision.candidate_entities if e.role == "subject"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && pytest tests/test_subject.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add api/app/models/schemas.py api/app/pipeline/subject.py api/tests/test_subject.py
git commit -m "feat: add primary subject + entity role to vision schema"
```

---

### Task 2: Vision prompts demand subject/collateral separation

**Files:**
- Modify: `api/app/ai/prompts.py` (`VISION_SYSTEM` ~lines 3-38, `TEXT_SIGNALS_SYSTEM` ~lines 85-93)
- Test: `api/tests/test_prompts.py` (create)

**Interfaces:**
- Consumes: nothing new (string constants).
- Produces: prompt strings that instruct the model to emit `primary_subject` and per-entity `role`.

This task has no behavioral unit under test beyond asserting the contract text is present (the strings drive an external LLM). Keep the test minimal.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_prompts.py
from app.ai import prompts


def test_vision_prompt_requires_primary_subject_and_roles():
    p = prompts.VISION_SYSTEM
    assert "primary_subject" in p
    assert '"role"' in p or "role" in p
    assert "collateral" in p


def test_text_prompt_requires_primary_subject():
    assert "primary_subject" in prompts.TEXT_SIGNALS_SYSTEM
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && pytest tests/test_prompts.py -v`
Expected: FAIL (`assert "primary_subject" in p`)

- [ ] **Step 3: Write minimal implementation**

Replace `VISION_SYSTEM` in `api/app/ai/prompts.py` with:

```python
VISION_SYSTEM = (
    "You extract structured signals from a shared image (usually a screenshot of a web page "
    "or social post). "
    'Return ONLY minified JSON of the form: '
    '{"detected_service":<enum>,"primary_subject":{"subject_type":<enum>,"title":<string|null>,'
    '"why":<string>},"visible_url":<string|null>,"title_guess":<string|null>,'
    '"ocr_text":<string>,"reasoning":<string>,'
    '"candidate_entities":[{"type":<string>,"value":<string>,"role":<"subject"|"collateral">}]} '
    'detected_service is the CONTAINER the item appeared in, one of ["github","imdb","movie",'
    '"youtube","twitter","instagram","tiktok","product","recipe","article","generic"]. '
    'primary_subject is what the capture is REALLY about, independent of the container: a movie '
    "or TV show promo posted on Instagram is still ABOUT that movie/show. "
    'primary_subject.subject_type is one of ["show","movie","repo","product","article","paper",'
    '"recipe","social","youtube","generic"] ("show" for a TV series, "movie" for a film). '
    "why is one short sentence saying why that is the subject. "
    "Every entity MUST carry a role: 'subject' if it is part of the real subject, 'collateral' "
    "for anything incidental - sponsored/ad blocks, app navigation or UI chrome, watermarks, and "
    "caption text unrelated to the subject. "
    "Entity types you may emit: repo, movie, media_title, person, character, provider, studio, "
    "year, imdb_id, url, product, other. Use 'media_title' for a film/series title, 'person' for "
    "an actor/creator, and 'provider' for a streaming service (e.g. 'Apple TV+', 'Netflix'). "
    "reasoning is one short sentence describing what you see. "
    'If you cannot tell the container, use "generic". Never output prose, markdown, or '
    "explanations outside the JSON.\n\n"
    "Example 1 - the github.com/facebook/react repository page:\n"
    '{"detected_service":"github","primary_subject":{"subject_type":"repo","title":"facebook/react",'
    '"why":"The page is the react repository"},"visible_url":"github.com/facebook/react",'
    '"title_guess":"facebook/react","ocr_text":"facebook/react  Public  The library for web and '
    'native user interfaces  230k stars","reasoning":"GitHub repo page for facebook/react",'
    '"candidate_entities":[{"type":"repo","value":"facebook/react","role":"subject"}]}\n'
    "Example 2 - the IMDb page for Dune: Part Two:\n"
    '{"detected_service":"imdb","primary_subject":{"subject_type":"movie","title":"Dune: Part Two",'
    '"why":"IMDb title page for the film"},"visible_url":"imdb.com/title/tt15239678",'
    '"title_guess":"Dune: Part Two","ocr_text":"Dune: Part Two  2024  PG-13  8.5/10",'
    '"reasoning":"IMDb title page for the film Dune: Part Two",'
    '"candidate_entities":[{"type":"movie","value":"Dune: Part Two","role":"subject"},'
    '{"type":"year","value":"2024","role":"subject"},'
    '{"type":"imdb_id","value":"tt15239678","role":"subject"}]}\n'
    "Example 3 - an Instagram reel promoting the Apple TV+ series Priscilla, with a 'Sponsored' "
    "energy-drink banner and app nav visible:\n"
    '{"detected_service":"instagram","primary_subject":{"subject_type":"show","title":"Priscilla",'
    '"why":"The reel promotes the Apple TV+ series Priscilla"},"visible_url":null,'
    '"title_guess":"Priscilla","ocr_text":"ANNETTE BENING PRISCILLA  Apple TV  Sponsored: '
    'ZapEnergy  Home Search Reels","reasoning":"Instagram reel promoting the Apple TV+ series '
    'Priscilla",'
    '"candidate_entities":[{"type":"media_title","value":"Priscilla","role":"subject"},'
    '{"type":"person","value":"Annette Bening","role":"subject"},'
    '{"type":"provider","value":"Apple TV+","role":"subject"},'
    '{"type":"other","value":"ZapEnergy","role":"collateral"}]}'
)
```

Replace `TEXT_SIGNALS_SYSTEM` with:

```python
TEXT_SIGNALS_SYSTEM = (
    "You extract lightweight signals from a shared text snippet. Return ONLY minified JSON: "
    '{"detected_service":<enum>,"primary_subject":{"subject_type":<enum>,"title":<string|null>,'
    '"why":<string>},"visible_url":<string|null>,"title_guess":<string|null>,'
    '"ocr_text":<string>,'
    '"candidate_entities":[{"type":<string>,"value":<string>,"role":<"subject"|"collateral">}]} '
    'detected_service must be one of ["github","imdb","movie","youtube","twitter","instagram",'
    '"tiktok","product","recipe","article","generic"]. '
    'primary_subject.subject_type is one of ["show","movie","repo","product","article","paper",'
    '"recipe","social","youtube","generic"] and describes what the text is really about. '
    'Put the original text in ocr_text. Every entity carries a role: "subject" or "collateral" '
    "(unrelated asides, promo/ad text). "
    'Entity types: repo, movie, year, imdb_id, url, product, person, media_title, provider, '
    'studio, character, other. '
    'If unsure, use "generic" and an empty candidate_entities. Never output prose.'
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && pytest tests/test_prompts.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add api/app/ai/prompts.py api/tests/test_prompts.py
git commit -m "feat: prompts extract primary subject and label collateral entities"
```

---

### Task 3: TV Shows as a first-class category

**Files:**
- Modify: `api/app/db.py:86-89` (`SEED_CATEGORIES`)
- Modify: `api/app/resolvers/movie.py:96-120` (`build_media_item` category hints)
- Modify: `api/app/ai/prompts.py` (`CATEGORIZE_SYSTEM` example trees)
- Test: `api/tests/test_media_builder.py` (add cases)

**Interfaces:**
- Consumes: `build_media_item(details: dict, media_type: str, pick_confidence: float) -> EnrichedItem`.
- Produces: TV payloads yield `category_hints == ["TV Shows"]`; movie payloads keep `["Movies"]`.

- [ ] **Step 1: Write the failing test**

Add to `api/tests/test_media_builder.py`:

```python
from app.resolvers.movie import build_media_item


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && pytest tests/test_media_builder.py -k "tv_show_filed or movie_stays" -v`
Expected: FAIL (`assert ["Movies"] == ["TV Shows"]`)

- [ ] **Step 3: Write minimal implementation**

`api/app/db.py` — add `"TV Shows"`:

```python
SEED_CATEGORIES = [
    "Development", "Links", "Movies", "TV Shows", "Articles", "Products",
    "Recipes", "Papers", "Social", "Inbox",
]
```

`api/app/resolvers/movie.py` — in `build_media_item`, change the `EnrichedItem(...)` return so `category_hints` depends on `is_tv`:

```python
        category_hints=["TV Shows"] if is_tv else ["Movies"],
```

`api/app/ai/prompts.py` — in `CATEGORIZE_SYSTEM`, add `"TV Shows"` to both example `"tree":[...]` arrays (after `"Movies"`), so the tree reads:
`["Development","Links","Movies","TV Shows","Articles","Products","Recipes","Papers","Social","Inbox"]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && pytest tests/test_media_builder.py -v`
Expected: PASS (existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add api/app/db.py api/app/resolvers/movie.py api/app/ai/prompts.py api/tests/test_media_builder.py
git commit -m "feat: file TV shows under a dedicated TV Shows category"
```

---

### Task 4: Resolve by subject, not container

**Files:**
- Modify: `api/app/resolvers/registry.py` (add subject-type routing to `pick`)
- Test: `api/tests/test_resolver_pick.py` (add case)

**Interfaces:**
- Consumes: `Resolver.id`, `Signals.vision.primary_subject.subject_type`, `Resolver.detect(signals)`.
- Produces: `pick(signals: Signals) -> Resolver` — when a confident `subject_type` maps to a
  registered resolver whose `detect()` clears `SUBJECT_ROUTE_FLOOR`, that resolver wins even if
  another scored higher on raw signals.

- [ ] **Step 1: Write the failing test**

Add to `api/tests/test_resolver_pick.py`:

```python
from app.models.schemas import PrimarySubject


def test_subject_type_routes_over_higher_container_score():
    # Weak movie signals (would lose to social on raw detect), but the subject is a film.
    vision = VisionResult(
        detected_service="instagram",
        primary_subject=PrimarySubject(subject_type="movie", title="Priscilla"),
        candidate_entities=[CandidateEntity(type="media_title", value="Priscilla")],
        ocr_text="film directed by someone",
    )
    sig = Signals(input_type="image",
                  canonical_url="https://www.instagram.com/reel/abc/", vision=vision)
    assert registry.pick(sig).id == "movie"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && pytest tests/test_resolver_pick.py -k subject_type -v`
Expected: FAIL (social wins, `assert 'social' == 'movie'`) — or PASS-by-accident; if it passes, weaken the movie signals until it fails first, then proceed.

- [ ] **Step 3: Write minimal implementation**

In `api/app/resolvers/registry.py`, add the map + routing. Above `pick`:

```python
# A confident primary-subject type routes straight to its resolver, so the container
# service (e.g. an Instagram post wrapping a film) cannot outvote the real subject.
SUBJECT_TYPE_TO_RESOLVER = {
    "movie": "movie", "show": "movie",
    "repo": "github", "product": "product", "article": "article",
    "paper": "paper", "recipe": "recipe", "social": "social", "youtube": "youtube",
}
# The mapped resolver still has to look at least plausible before we trust the route.
SUBJECT_ROUTE_FLOOR = 0.3
```

Replace `pick` with:

```python
def pick(signals: Signals) -> Resolver:
    resolvers = all_resolvers()
    by_id = {r.id: r for r in resolvers}
    generic = by_id.get("generic")

    scores: dict[str, float] = {}
    for r in resolvers:
        if r.id == "generic":
            continue
        try:
            scores[r.id] = r.detect(signals)
        except Exception as exc:
            log.warning("resolver %s detect failed: %s", r.id, exc)
    for rid, sc in scores.items():
        log.info("detect %s -> %.2f", rid, sc)

    # Subject-first routing.
    subject = signals.vision.primary_subject if signals.vision else None
    if subject:
        target = SUBJECT_TYPE_TO_RESOLVER.get(subject.subject_type)
        if target and target in by_id and scores.get(target, 0.0) >= SUBJECT_ROUTE_FLOOR:
            return by_id[target]

    best = max(scores.items(), key=lambda kv: kv[1], default=None)
    if best and best[1] >= MIN_DETECT:
        return by_id[best[0]]
    assert generic is not None, "generic resolver must be registered"
    return generic
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && pytest tests/test_resolver_pick.py -v`
Expected: PASS (existing 3 + new)

- [ ] **Step 5: Commit**

```bash
git add api/app/resolvers/registry.py api/tests/test_resolver_pick.py
git commit -m "feat: route resolution by primary subject over container service"
```

---

### Task 5: Movie resolver — use subject entities + graceful enrich miss

**Files:**
- Modify: `api/app/resolvers/movie.py` (`title_year_from_signals`, `enrich` miss paths)
- Test: `api/tests/test_media_detect.py` (add), `api/tests/test_movie_enrich_miss.py` (create)

**Interfaces:**
- Consumes: `subject_entities(vision)` from `app.pipeline.subject`; `PrimarySubject`.
- Produces: on an enrich miss, `EnrichedItem` carrying the known `title`/`description` and
  `attributes["_enrich_incomplete"] = <reason>`; reasons: `"No TMDb API key configured"`,
  `"No confident match on TMDb"`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_movie_enrich_miss.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && pytest tests/test_movie_enrich_miss.py -v`
Expected: FAIL (title is `signals.title` which is None, and no `_enrich_incomplete` key)

- [ ] **Step 3: Write minimal implementation**

In `api/app/resolvers/movie.py`:

Add import at top:

```python
from ..pipeline.subject import subject_entities
```

Add a helper near `title_year_from_signals`:

```python
def _subject_title(signals: Signals) -> str | None:
    """Best-known subject title without a TMDb hit: primary subject, then vision, then source."""
    if signals.vision and signals.vision.primary_subject and signals.vision.primary_subject.title:
        return signals.vision.primary_subject.title
    title, _ = title_year_from_signals(signals)
    return title


def _subject_description(signals: Signals) -> str | None:
    ps = signals.vision.primary_subject if signals.vision else None
    if ps and ps.why:
        return ps.why
    if signals.vision and signals.vision.ocr_text:
        return signals.vision.ocr_text[:280].strip() or None
    return None
```

Update `title_year_from_signals` to read only subject entities — change its entity loop to iterate `subject_entities(signals)`:

```python
def title_year_from_signals(signals: Signals) -> tuple[str | None, str | None]:
    title = None
    year = None
    if signals.vision:
        for ent in subject_entities(signals.vision):
            if ent.type in ("movie", "media_title") and not title:
                title = ent.value
            if ent.type == "year" and not year:
                year = ent.value
        title = title or signals.vision.title_guess
    title = title or signals.og.get("og:title") or signals.title
    return title, year
```

Rewrite the two miss branches in `enrich`:

```python
    async def enrich(self, signals: Signals) -> EnrichedItem:
        api_key = get_settings().tmdb_api_key
        if not api_key:
            return EnrichedItem(
                type="movie", title=_subject_title(signals),
                description=_subject_description(signals),
                attributes={"_enrich_incomplete": "No TMDb API key configured"},
                confidence=0.2,
            )

        async with httpx.AsyncClient(timeout=20.0) as client:
            tmdb_id, media_type, pick_confidence = await self._identify(client, api_key, signals)
            if tmdb_id is None:
                return EnrichedItem(
                    type="movie", title=_subject_title(signals),
                    description=_subject_description(signals),
                    attributes={"_enrich_incomplete": "No confident match on TMDb"},
                    confidence=min(pick_confidence, 0.3),
                )

            details = (await client.get(
                f"{TMDB}/{media_type}/{tmdb_id}",
                params={"api_key": api_key,
                        "append_to_response": "videos,external_ids,credits,watch/providers"},
            )).json()

        return build_media_item(details, media_type, pick_confidence)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && pytest tests/test_movie_enrich_miss.py tests/test_media_detect.py -v`
Expected: PASS (new test + existing detect tests still green)

- [ ] **Step 5: Commit**

```bash
git add api/app/resolvers/movie.py api/tests/test_movie_enrich_miss.py
git commit -m "feat: keep subject info and flag reason when TMDb enrich misses"
```

---

### Task 6: Provenance narrates by subject; drop internal classify step

**Files:**
- Modify: `api/app/pipeline/provenance.py` (`describe_resolve`, `describe_vision`)
- Modify: `api/app/pipeline/run.py:41-51` (remove the user-facing `classify` step; keep `describe_resolve` call site)
- Test: `api/tests/test_provenance_describe.py` (update expectations)

**Interfaces:**
- Consumes: `describe_resolve(resolver_id: str, score: float, subject_type: str | None = None)`.
- Produces: TV/film phrasing in `describe_resolve`; comprehension phrasing in `describe_vision`.

- [ ] **Step 1: Update the failing tests**

In `api/tests/test_provenance_describe.py`, replace `test_describe_resolve_formats_score` and add a TV case; update `describe_vision` import usage:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && pytest tests/test_provenance_describe.py -v`
Expected: FAIL (`describe_resolve` takes 2 args; no subject phrasing)

- [ ] **Step 3: Write minimal implementation**

In `api/app/pipeline/provenance.py`:

```python
_SUBJECT_NOUN = {
    "show": "a TV show", "movie": "a film", "repo": "a code repository",
    "product": "a product", "article": "an article", "paper": "a paper",
    "recipe": "a recipe", "social": "a social post", "youtube": "a video",
}


def describe_resolve(resolver_id: str, score: float, subject_type: str | None = None) -> tuple[str, str]:
    noun = _SUBJECT_NOUN.get(subject_type or "")
    summary = f"Matched as {noun}" if noun else f"Matched by the {resolver_id} resolver"
    return summary, f"score={score:.2f}"
```

Update `describe_vision` to narrate the subject and any dropped collateral:

```python
def describe_vision(signals: Signals) -> tuple[str, str | None]:
    v = signals.vision
    service = v.detected_service if v else "generic"
    ps = v.primary_subject if v else None
    if ps and ps.title:
        summary = f"Saw {service}; the subject is {ps.title}"
    elif ps and ps.subject_type not in (None, "generic"):
        summary = f"Saw {service}; the subject looks like a {ps.subject_type}"
    else:
        summary = f"Vision: detected {service}"
    if v and any(e.role == "collateral" for e in v.candidate_entities):
        summary += " (ignored unrelated ad/caption text)"
    detail = None
    if v:
        detail = v.reasoning or (v.ocr_text[:120].strip() or None)
    return summary, detail
```

In `api/app/pipeline/run.py`: remove the user-facing classify provenance line and pass `subject_type` to `describe_resolve`.

Delete this line (was ~line 47):

```python
        prov.add("classify", f"Classified input as {signals.input_type}")
```

Change the resolve-describe call (was ~line 61) to:

```python
        subject_type = (signals.vision.primary_subject.subject_type
                        if signals.vision and signals.vision.primary_subject else None)
        rs, rd = prov_desc.describe_resolve(resolver.id, score, subject_type)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && pytest tests/test_provenance_describe.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/pipeline/provenance.py api/app/pipeline/run.py api/tests/test_provenance_describe.py
git commit -m "feat: narrate provenance by subject and drop internal classify step"
```

---

### Task 7: Frontend attrs — curated key-facts + meta line

**Files:**
- Modify: `web/src/lib/attrs.ts`
- Test: `web/src/lib/attrs.test.ts` (update `attrRows` expectations, add `metaLine`)

**Interfaces:**
- Produces: `attrRows(attributes)` returns only allow-listed key-facts rows (`cast`,
  `provider`→"Where to watch", `network`, `genres`); `metaLine(item: {type, attributes})`
  returns a string like `"2026 · 42 min · 7.8 ★ · Show"` from `year/runtime/rating/type`.

- [ ] **Step 1: Update the failing test**

Replace the `attrRows` describe block in `web/src/lib/attrs.test.ts` and add a `metaLine` block:

```typescript
import { attrRows, compactNum, formatScalar, humanizeKey, linkKeyLabel, linkLabel, metaLine } from "./attrs";

describe("attrRows key-facts", () => {
  it("renders only curated facts as labeled chips, hides everything else", () => {
    const rows = attrRows({
      type: "show", rating: 7.8, year: "2026", runtime: 42,
      cast: ["Annette Bening", "Someone Else"],
      provider: ["Apple TV+"], network: ["Apple TV+"], genres: ["Drama"],
      tmdb_id: 220000, apple_original: true, _enrich_incomplete: "x",
    });
    const byKey = Object.fromEntries(rows.map((r) => [r.key, r]));

    expect(byKey.cast.label).toBe("Cast");
    expect(byKey.provider.label).toBe("Where to watch");
    expect(byKey.network.label).toBe("Network");
    expect(byKey.genres.label).toBe("Genres");

    // meta-line + internal + noise keys never appear as rows
    for (const k of ["rating", "year", "runtime", "type", "tmdb_id", "apple_original", "_enrich_incomplete"]) {
      expect(byKey[k]).toBeUndefined();
    }
  });
});

describe("metaLine", () => {
  it("assembles known facts, skipping unknowns", () => {
    expect(metaLine({ type: "show", attributes: { year: "2026", runtime: 42, rating: 7.8 } }))
      .toBe("2026 · 42 min · 7.8 ★ · Show");
    expect(metaLine({ type: "movie", attributes: {} })).toBe("Movie");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- attrs`
Expected: FAIL (`metaLine` undefined; `attrRows` still returns rating/year rows)

- [ ] **Step 3: Write minimal implementation**

In `web/src/lib/attrs.ts`, replace `attrRows` and add `metaLine`. Keep `compactNum`, `humanizeKey`, `formatScalar`, `linkLabel`, `linkKeyLabel` as-is.

```typescript
// Only these attributes render as key-facts rows, in this order, with these labels.
const KEY_FACTS: { key: string; label: string }[] = [
  { key: "cast", label: "Cast" },
  { key: "provider", label: "Where to watch" },
  { key: "network", label: "Network" },
  { key: "genres", label: "Genres" },
];

export function attrRows(attributes: Record<string, unknown>): AttrRow[] {
  const rows: AttrRow[] = [];
  for (const { key, label } of KEY_FACTS) {
    const v = attributes?.[key];
    if (Array.isArray(v)) {
      const chips = v.filter((x) => x != null && x !== "").map(String);
      if (chips.length) rows.push({ key, label, kind: "chips", chips });
    } else if (v != null && v !== "") {
      rows.push({ key, label, kind: "text", text: formatScalar(key, v) });
    }
  }
  return rows;
}

const TYPE_LABEL: Record<string, string> = { show: "Show", movie: "Movie" };

// One muted line under the title: year · runtime · rating · type. Skips unknowns.
export function metaLine(item: { type: string; attributes: Record<string, unknown> }): string {
  const a = item.attributes || {};
  const parts: string[] = [];
  if (a.year) parts.push(String(a.year));
  if (typeof a.runtime === "number") parts.push(`${a.runtime} min`);
  if (typeof a.rating === "number") parts.push(`${a.rating.toFixed(1)} ★`);
  const t = TYPE_LABEL[item.type] || humanizeKey(item.type);
  if (t) parts.push(t);
  return parts.join(" · ");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test -- attrs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/attrs.ts web/src/lib/attrs.test.ts
git commit -m "feat: curate detail key-facts and add subject meta line"
```

---

### Task 8: Provenance component — plain summary + technical details toggle

**Files:**
- Modify: `web/src/components/Provenance.tsx`
- Test: `web/src/components/Provenance.test.tsx` (create)

**Interfaces:**
- Consumes: `ProvStep[]` (`{ stage, summary, detail? }`).
- Produces: renders `summary` inline; renders `detail` inside a nested `<details>` labeled
  "Technical details", not inline.

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/components/Provenance.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Provenance from "./Provenance";

describe("Provenance", () => {
  it("shows summaries and tucks technical detail behind a toggle", () => {
    render(<Provenance steps={[{ stage: "resolve", summary: "Matched as a film", detail: "score=0.90" }]} />);
    expect(screen.getByText("Matched as a film")).toBeTruthy();
    // detail text lives under a "Technical details" summary element
    expect(screen.getByText("Technical details")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- Provenance`
Expected: FAIL (no "Technical details" element)

- [ ] **Step 3: Write minimal implementation**

Replace the `detail` rendering in `web/src/components/Provenance.tsx`:

```tsx
              {s.detail && (
                <details className="mt-0.5">
                  <summary className="cursor-pointer text-[11px] text-slate-600">
                    Technical details
                  </summary>
                  <div className="text-xs text-slate-500">{s.detail}</div>
                </details>
              )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test -- Provenance`
Expected: PASS

If `@testing-library/react` is not installed, verify with `cd web && npm ls @testing-library/react`; if absent, skip the render test and instead assert the component module exports a default function (`expect(typeof Provenance).toBe("function")`) — do not add new dependencies in this plan.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/Provenance.tsx web/src/components/Provenance.test.tsx
git commit -m "feat: hide provenance technical numbers behind a toggle"
```

---

### Task 9: Detail panel — subject card layout + incomplete banner

**Files:**
- Modify: `web/src/pages/Item.tsx`
- Test: manual (UI composition); covered by `attrs`/`Provenance` unit tests above.

**Interfaces:**
- Consumes: `metaLine`, `attrRows` (Task 7); `item.attributes._enrich_incomplete`.
- Produces: rendered card — hero, title + meta line, incomplete banner, description, links,
  key facts, provenance.

- [ ] **Step 1: Implement the layout changes**

In `web/src/pages/Item.tsx`:

Add `metaLine` to the import from `../lib/attrs`:

```tsx
import { attrRows, linkKeyLabel, linkLabel, metaLine } from "../lib/attrs";
```

After the existing `rows`/`links` derivation, add:

```tsx
  const meta = metaLine(item);
  const incomplete = (item.attributes as Record<string, unknown>)?._enrich_incomplete as string | undefined;
```

Under the `<h1>` title, add the meta line:

```tsx
          <h1 className="text-xl font-semibold">{item.title || "Untitled"}</h1>
          {meta && <div className="mt-0.5 text-sm text-slate-500">{meta}</div>}
```

Directly after the title/links block (before the description), add the incomplete banner:

```tsx
      {incomplete && (
        <div className="mt-3 rounded-lg border border-amber-700/50 bg-amber-900/20 p-3 text-sm text-amber-300">
          Couldn't fetch full details — {incomplete}.
        </div>
      )}
```

Leave the existing description, tags/categories, key-facts `<dl>` (now fed by the curated
`attrRows`), and `<Provenance>` blocks in place and in that order.

- [ ] **Step 2: Typecheck + build**

Run: `cd web && npm run build`
Expected: build succeeds (no TS errors)

- [ ] **Step 3: Run the frontend test suite**

Run: `cd web && npm test`
Expected: PASS (all suites)

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/Item.tsx
git commit -m "feat: render item detail as a subject card with incomplete banner"
```

---

### Task 10: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Backend suite**

Run: `cd api && pytest`
Expected: all PASS

- [ ] **Step 2: Frontend suite + build**

Run: `cd web && npm test && npm run build`
Expected: all PASS, build succeeds

- [ ] **Step 3: Commit any incidental fixes**

If earlier tasks left a test needing an update (e.g. an old `attrRows` assertion), fix it now
and commit:

```bash
git add -A
git commit -m "test: reconcile suites with subject-card + comprehension changes"
```

---

## Notes for the implementer

- Old `attrRows` tests in `web/src/lib/attrs.test.ts` (rendering arbitrary attributes like
  `language`, `apple_original`) are **replaced** by Task 7's curated behavior — update, don't
  keep both. `formatScalar`/`humanizeKey`/`linkLabel` tests stay valid.
- The `HIDDEN_KEYS`/`COMPACT_KEYS`/`KEY_LABELS` constants in `attrs.ts` may still be referenced
  by `formatScalar`/`humanizeKey`; keep whatever those helpers use, drop only what `attrRows`
  no longer needs.
- No new npm or pip dependencies. If a frontend render-test helper is missing, fall back to the
  export-shape assertion described in Task 8.
