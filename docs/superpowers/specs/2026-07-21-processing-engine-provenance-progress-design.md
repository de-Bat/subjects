# Design: Smarter Processing Engine + Provenance + Progress Bar

Date: 2026-07-21
Status: Approved (brainstorming), pending spec review

## Problem

The processing engine resolves shared screenshots too weakly.

Motivating case: an Instagram Reel from **Apple TV** showing **Annette Bening** in **Priscilla**
(caption "Annette Bening is in her villain era…"). The user expects to later query
"TV shows/movies with Bening that are Apple originals" and to see a media short description
plus *how the system got there*.

Today that screenshot fails:

- Instagram is not in the vision `detected_service` enum → vision returns `generic`/`twitter`.
- The `social` resolver matches only twitter/x/mastodon/bsky/threads/linkedin hosts — **not
  instagram** → the item falls through to `generic`.
- The `movie` resolver searches TMDb **movies only** (`/search/movie`); *Priscilla* is a **TV
  show** → miss. It also never captures cast or streaming provider, so "with Bening" and
  "apple originals" are not queryable.
- No reasoning/provenance is stored anywhere → no "how I got there".
- The pipeline emits SSE `stage` events, but the UI shows only a status word — no progress feedback.

A second, related complaint (github screenshots): the engine should reliably resolve a github
screenshot to the **real repo** and attach the github / repo icon. The `github` resolver already
resolves owner/repo and sets `icon_url` to the owner avatar, so the gap is (a) extraction
reliability reaching the resolver and (b) a guaranteed icon fallback.

## Goals

1. The Bening screenshot resolves to a rich **media** item: type=show, cast incl. Annette Bening,
   provider = Apple TV+, marked apple-original, with a short description — and is findable via the
   existing search by actor + provider.
2. Every item carries a **provenance trace** ("how I got there"): a per-stage step log plus a
   one-line rationale, rendered on the item detail page.
3. The item detail page shows a **stage-segmented progress bar** while the item is processing.
4. GitHub screenshots reliably resolve to the repo with a guaranteed icon.

## Non-goals (YAGNI)

- No progress bar on Inbox list cards (item detail page only).
- No dedicated faceted/filter search UI — reuse existing Meilisearch/Search page via tags.
- No full free-text LLM narrative for provenance — structured step log + one-line rationale only.
- No rewrite of every resolver. Media + github are the focus; the provenance layer is generic
  and applies to all resolvers for free.

---

## Part 1 — Extraction engine upgrade (media-first, generalizable)

### 1a. Richer vision extraction

`api/app/ai/prompts.py` — `VISION_SYSTEM`:

- Extend `detected_service` enum with `instagram`, `tiktok`. Keep the existing values and the
  `generic` fallback. Instruct: detect the **service/container** (instagram, tiktok, imdb…) *and*
  the **subject** independently — a movie/show promo posted on Instagram is still about a movie/show.
- Expand `candidate_entities` guidance to emit these entity `type`s:
  `person` (a.k.a. actor), `media_title`, `character`, `provider` (streaming service such as
  "Apple TV+", "Netflix"), `studio`. Keep existing `repo`, `movie`, `year`, `imdb_id`, `url`,
  `product`, `other`.
- Add one example: an Instagram media-promo screenshot →
  `detected_service:"instagram"`, entities include `{person:"Annette Bening"}`,
  `{media_title:"Priscilla"}`, `{provider:"Apple TV+"}`.

`api/app/models/schemas.py` — `VisionResult`:

- Add `reasoning: str = ""` — one line describing what the VLM sees (seeds provenance).

Backwards compatible: extra enum values and entity types are strings; existing resolvers ignore
what they do not use.

### 1b. `movie` resolver → `media` (movies **and** TV)

`api/app/resolvers/movie.py`. Keep resolver `id = "movie"` for continuity (no data migration of
existing items required) but broaden behavior; `item_type` becomes `movie` or `show` per result.

`detect()` additions — return a high score (≥0.85) when vision signals describe media even without
"movie" keywords:

- Existing: imdb id / `detected_service in (imdb, movie)` / ≥2 MOVIE_WORDS.
- New: vision has a `media_title` entity **and** (a `person`/`actor` entity **or** a `provider`
  entity). This is what lets the Instagram-Bening case pick media over social/generic.

`_identify()` — search both endpoints:

- Query TMDb `/search/movie` **and** `/search/tv` (using title, and year when present).
- Present both candidate sets to the LLM pick with a `media_type` field per candidate.
- `MoviePick` schema gains `media_type: Literal["movie","tv"] | None`. Validate the picked id
  belongs to the candidate set of the chosen media_type (existing hallucination guard, per type).

`enrich()` — for the chosen id:

- movie: `GET /movie/{id}?append_to_response=videos,external_ids,credits,watch/providers`
- tv: `GET /tv/{id}?append_to_response=videos,external_ids,credits,watch/providers`
- Normalize the differences: `title` vs `name`, `release_date` vs `first_air_date`,
  `runtime` vs `episode_run_time[0]`, plus `networks` (tv only).
- Attributes: `type` (`movie`|`show`), `rating`, `votes`, `year`, `tmdb_id`,
  `cast` (top ~8 names from credits), `provider` (flatrate provider names from
  watch/providers, region `US`), `network` (tv), `apple_original` (bool: true when a provider
  is Apple TV+ — best-effort heuristic).
- Tags: existing genre + year, plus `actor:<slugified name>` for top cast, `provider:<slug>` per
  provider (e.g. `provider:apple-tv+`), and `apple-original` when the flag is set. These tags are
  what make "annette bening apple" searchable via the existing Meilisearch index.
- `canonical_url` / poster / trailer as today, using the movie-or-tv path.

### 1c. Social resolver — add hosts, yield to media

`api/app/resolvers/social.py`:

- Add `instagram\.com`, `tiktok\.com`, `threads\.net` to `SOCIAL_HOSTS`.
- Add `instagram`/`tiktok` to the `detected_service` check.
- **Yield to media:** the registry already picks argmax of `detect()`. Because 1b makes the media
  resolver score ≥0.85 when a media_title+person/provider is present, and social scores ~0.7–0.85
  on container alone, media wins for promo posts. No special-casing needed beyond keeping social's
  container-only score at/below media's content score. Document this ordering assumption in a comment.

### 1d. GitHub icon guarantee

`api/app/resolvers/github.py` — in `enrich()`, when the GitHub API avatar is missing, fall back to
`https://github.com/<owner>.png` for both `icon_url` and `thumbnail_url`. (Extraction reliability is
handled by the richer vision prompt in 1a; the resolver already resolves owner/repo and sets the
avatar when present.)

---

## Part 2 — Provenance ("How I got there")

### Data model

`api/app/models/schemas.py`:

```python
class ProvStep(BaseModel):
    stage: str          # "vision" | "classify" | "resolve" | "enrich" | "why" | "dedup" | "finalize"
    summary: str        # one line, user-facing
    detail: str | None = None   # optional extra (scores, ids)

class Provenance(BaseModel):
    steps: list[ProvStep] = Field(default_factory=list)
    def add(self, stage: str, summary: str, detail: str | None = None) -> None: ...
```

### Threading & persistence

`api/app/pipeline/run.py` creates one `Provenance` per pipeline run and passes it into each stage
(extract, resolve_and_enrich, categorize). Each stage appends a step:

- **vision**: detected_service + short OCR/`reasoning` snippet.
- **classify**: chosen item type.
- **resolve**: resolver id + detect score (e.g. `"resolver=movie score=0.90"`).
- **enrich**: the concrete match (e.g. `"TMDb tv #… Priscilla (2026)"`) + key fields captured.
- **why**: one-line rationale — assembled from the winning signals (title+actor matched, provider
  confirmed). No extra LLM call in the default path; derived from the resolver result. (If a
  resolver already made an LLM pick, its confidence feeds this line.)
- **dedup / finalize**: duplicate-of, or final status + confidence vs threshold.

Persisted via `enrich.py` into `attributes["_provenance"] = prov.model_dump()["steps"]`
(JSONB `attributes` is already a free-form dict — **no schema migration**). The leading underscore
marks it as engine metadata; the Item page renders it specially and the generic attribute table
skips keys beginning with `_`.

### Frontend

`web/src/components/Provenance.tsx` — a collapsible "How I got there" section on the item page:
numbered steps (stage label + summary, detail shown muted). Rendered from
`item.attributes._provenance`. `web/src/pages/Item.tsx` filters `_`-prefixed keys out of the
generic attribute `<dl>` and mounts `<Provenance>` instead.

---

## Part 3 — Progress bar (item detail page only)

### Backend

`api/app/pipeline/run.py` already emits `item.updated {stage, status}` after each stage. Add
explicit emits for the two currently-implicit stages so the bar has full resolution:
`classify` (after vision, before resolve) and `resolve` (after resolver pick, before persist).
Canonical ordered stage list:
`["classify", "extract", "resolve", "enrich", "categorize", "dedup", "finalize"]`.

### Frontend

`web/src/components/ProcessingProgress.tsx`:

- Props: current item status + a live `stage` from SSE.
- Maintain `latestStageIndex` from incoming SSE `stage` values (mapped against the ordered list).
- Render a segmented bar: filled up to `latestStageIndex`, current segment pulsing.
- Terminal handling: `enriched`/`needs_review`/`duplicate` → bar completes (all filled) then the
  component hides after a short delay; `error`/`failed` → final segment red.
- On page load of an **already-terminal** item (status not in {pending, processing}) → render nothing.

`web/src/pages/Item.tsx`: the existing SSE subscription already reloads on `item_id` match; extend
its handler to also feed `ev.stage` into `ProcessingProgress`. Mount the bar above the title while
status ∈ {pending, processing}.

`web/src/lib/api.ts`: extend the SSE event type with optional `stage`/`status` fields;
`Item.attributes` already typed as a dict, so `_provenance` needs only a light type helper.

---

## Data flow (end to end)

```
ingest → item(pending)
  run_pipeline(prov):
    extract(source, prov)                → SSE {stage:classify} , {stage:extract}
    resolve_and_enrich(signals, prov)    → SSE {stage:resolve}  , {stage:enrich}
    categorize(session, enriched, prov)  → SSE {stage:categorize}
    dedup                                → SSE {stage:dedup}  (if duplicate)
    finalize (confidence gate)           → SSE {stage:finalize, status}
  persist: attributes._provenance = prov.steps
Frontend Item page:
  SSE stage events   → ProcessingProgress fills
  SSE item.updated   → reload item → render Provenance + final state
```

## Testing

Backend (pytest, existing resolver-test pattern):

- media resolver TV branch: mock TMDb `/search/tv`, `/tv/{id}` (credits + watch/providers) →
  asserts `type=show`, cast contains the actor, `provider` contains "Apple TV+",
  `apple_original` true, tags include `actor:…` and `provider:apple-tv+`.
- media `detect()`: vision with `media_title`+`person` scores ≥0.85 (beats social's container score).
- provenance accumulation: a run appends the expected ordered stages; `_provenance` persisted in
  `attributes`.
- github icon fallback: missing avatar → `https://github.com/<owner>.png`.

Frontend (vitest, existing pattern):

- `ProcessingProgress`: stage→segment index mapping; terminal statuses fill/hide; error → red.
- `Provenance`: renders steps from `attributes._provenance`; generic attribute table skips
  `_`-prefixed keys.

## Files touched

- `api/app/ai/prompts.py` — richer VISION_SYSTEM; media pick prompt (movie+tv).
- `api/app/models/schemas.py` — VisionResult.reasoning; MoviePick.media_type; ProvStep/Provenance.
- `api/app/resolvers/movie.py` — tv search, cast, providers, media detect, tags.
- `api/app/resolvers/social.py` — instagram/tiktok/threads hosts; yield-to-media comment.
- `api/app/resolvers/github.py` — avatar fallback.
- `api/app/pipeline/run.py` — provenance threading; classify/resolve SSE emits.
- `api/app/pipeline/extract.py`, `resolve.py`, `categorize.py`, `enrich.py` — accept/append
  provenance; persist `_provenance`.
- `web/src/components/ProcessingProgress.tsx` (new), `web/src/components/Provenance.tsx` (new).
- `web/src/pages/Item.tsx` — mount both; filter `_`-prefixed attrs.
- `web/src/lib/api.ts` — SSE event stage/status typing.
