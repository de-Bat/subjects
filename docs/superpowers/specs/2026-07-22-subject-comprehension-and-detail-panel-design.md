# Subject Comprehension + Detail Panel — Design

Date: 2026-07-22

## Problem

Three user-reported issues with the capture pipeline and detail view:

1. **Detail panel is cluttered / JSON-like.** Core subject metadata (name, description,
   image, links) is not clearly foregrounded; provenance exposes raw technical numbers
   (`score=0.85`, `confidence 0.90 >= threshold 0.70`) and internal steps
   (`Classified input as image`).
2. **Basic subject info is missing.** TV shows can render with no description / image /
   link. When the TMDb lookup misses (no API key, no candidate, or the identifier defaults
   to the wrong media type) the item falls back to a bare title with an empty card, and the
   user cannot tell why.
3. **The engine is not smart enough.** It mislabels — provenance narrates "TV show" while
   the item is filed under Movies. More broadly the engine does not clearly (a) grasp what
   the capture is *really about*, (b) separate the real subject from collateral noise (ads,
   nav chrome, unrelated caption text), (c) categorize it correctly, then (d) connect dots /
   fill gaps from what it gathered.

## Goals

- The detail panel presents the **subject** as the star: image, name, description, links,
  and a curated set of key facts — always clearly shown, never a raw attribute dump.
- TV shows are categorized and narrated as TV, distinct from films.
- The engine forms an explicit **primary subject** understanding, separating subject from
  collateral, and resolves by the subject rather than the container it appeared in.
- When enrichment cannot complete, the item still shows whatever is known and a clear reason
  it is incomplete.

## Non-Goals

- No new resolver types. No change to the ingest/share path, SSE transport, or dedup.
- No multi-subject captures (one primary subject per item stays the model).
- No re-training / model swap; comprehension improvements are prompt + schema + routing.

---

## Part 1 — TV Shows as a first-class category

**Cause.** `SEED_CATEGORIES` (`api/app/db.py`) has no TV entry; `build_media_item`
(`api/app/resolvers/movie.py`) hard-codes `category_hints=["Movies"]` for both media types;
the categorize prompt's example tree omits TV. So a TV show (correctly typed `show`) is still
filed under **Movies**, and `describe_resolve` narrates "the movie resolver".

**Changes.**
- `db.py`: add `"TV Shows"` to `SEED_CATEGORIES`.
- `movie.py` `build_media_item`: `category_hints = ["TV Shows"] if is_tv else ["Movies"]`.
- `prompts.py` `CATEGORIZE_SYSTEM`: add `"TV Shows"` to the example trees so the LLM can
  select it; keep the movie example filing under Movies.
- `provenance.py` `describe_resolve`: narrate by **media/subject type**, not resolver id —
  e.g. "Matched as a TV show" / "Matched as a film" instead of "Matched by the movie
  resolver". Signature gains the enriched/subject type so it can phrase correctly.

Seeding is idempotent (existing categories are not duplicated); adding a new seed name only
inserts the missing row on next migration.

---

## Part 2 — Subject comprehension core

### 2.1 A focused subject on the vision result

Extend `VisionResult` (`api/app/models/schemas.py`):

```python
class PrimarySubject(BaseModel):
    subject_type: str = "generic"   # show, movie, repo, product, article, paper, recipe, social, generic
    title: str | None = None
    why: str | None = None          # one short sentence: why this is the real subject

class CandidateEntity(BaseModel):
    type: str
    value: str
    role: Literal["subject", "collateral"] = "subject"   # collateral = ad / chrome / unrelated

class VisionResult(BaseModel):
    detected_service: str = "generic"   # the CONTAINER (instagram, imdb, github...)
    primary_subject: PrimarySubject | None = None
    visible_url: str | None = None
    title_guess: str | None = None
    ocr_text: str = ""
    reasoning: str = ""
    candidate_entities: list[CandidateEntity] = Field(default_factory=list)
```

`role` defaults to `"subject"` so older payloads and simple captures need no special handling.
`primary_subject` is optional; when the model cannot decide, downstream falls back to today's
behavior (title_guess + entities).

### 2.2 Prompts demand subject/collateral separation

`VISION_SYSTEM` and `TEXT_SIGNALS_SYSTEM` (`prompts.py`):
- Require `primary_subject` with `subject_type`, `title`, `why`.
- Require every entity to carry `role`: `"subject"` for anything about the real subject,
  `"collateral"` for ads, sponsored blocks, app nav/chrome, and caption text unrelated to the
  subject.
- Add an example: a screenshot of an Instagram show promo that also contains a "Sponsored"
  ad banner and unrelated UI text — the show is `primary_subject`, the ad + chrome entities
  are `role:"collateral"`.
- `subject_type` enum documented so it maps cleanly to resolver ids.

### 2.3 Resolve by subject, not container

`registry.pick` (`api/app/resolvers/registry.py`):
- Build a `subject_type -> resolver.id` map from the registered resolvers (movie/show →
  `movie`, repo → `github`, product → `product`, article → `article`, paper → `paper`,
  recipe → `recipe`, social → `social`, youtube → `youtube`).
- If `signals.vision.primary_subject.subject_type` maps to a registered resolver, prefer that
  resolver, using its `detect()` score as confirmation. If that resolver's `detect()` is not
  hopeless (≥ a low floor), route to it even when another resolver (e.g. `social`, matching
  the container) scored higher on raw signals.
- Otherwise fall back to today's argmax-of-`detect()`.

This is the fix for "container beats subject": a movie/show promo shared from Instagram
resolves as the film/show, not as a generic social post.

### 2.4 Collateral is dropped downstream

- `movie.py` `title_year_from_signals` and any entity consumers iterate only
  `role == "subject"` entities (helper: `subject_entities(vision)`).
- Categorize/tag inputs exclude collateral so ad brands / unrelated hashtags don't become
  tags.

### 2.5 Connect dots / fill gaps on enrichment miss

When a resolver's canonical lookup cannot complete, merge the comprehension result instead of
returning a bare title:

- `movie.py` `enrich`: on a miss (no TMDb key, no candidate, invalid pick) return an
  `EnrichedItem` that still carries `title` (from `primary_subject`/vision), any vision
  thumbnail/screenshot as `thumbnail_url`, `description` from `primary_subject.why` or OCR
  summary, and sets `attributes["_enrich_incomplete"] = <reason>` with a low confidence.
- Reason strings are human: `"No TMDb API key configured"`, `"No confident match on TMDb"`.

The item is then gated to `needs_review` by the existing confidence threshold, and the panel
(Part 3) surfaces the reason.

### 2.6 Narrated provenance

`provenance.py`:
- `describe_vision`: when `primary_subject` present, narrate the comprehension —
  "Instagram post; the subject is the TV show *Priscilla*" and, if any collateral was
  dropped, "(ignored an ad and unrelated caption)".
- `describe_classify` step is **removed from the user-facing trace** (input_type image/url/text
  is internal). Keep vision/resolve/enrich/why/categorize/finalize.

---

## Part 3 — Detail panel as a structured subject card

Rework `web/src/pages/Item.tsx` and `web/src/lib/attrs.ts` so the subject is the star.

### Layout (top to bottom)

1. **Hero image** — `thumbnail_url` (poster/screenshot) prominent; icon-letter fallback when
   none. (Exists; keep, ensure always attempted.)
2. **Title + meta line** — title, then one muted line assembled from known facts:
   `year · runtime · rating ★ · type`. Assembled by a helper, not dumped as separate rows.
3. **Incomplete banner** — when `attributes._enrich_incomplete` is set, an amber notice:
   "Couldn't fetch full details — {reason}." Shown above the description so an empty-ish card
   is explained, never blank-and-confusing.
4. **Description** — full overview as a clean paragraph. (Exists.)
5. **Links** — canonical + trailer + IMDb + homepage as pills. (Exists.)
6. **Key facts** — a curated, labeled block for the fields that matter, humanized, chips
   where multi-valued: **Cast**, **Where to watch** (providers), **Network** (TV), **Genres**.
   Driven by an allow-list of meaningful keys, not a dump of every attribute.
7. **Provenance** — "How I got there", plain-language sentences by default. Raw technical
   numbers (scores/thresholds) move behind a nested **"Technical details"** toggle inside the
   existing `<details>`.

### `attrs.ts` changes

- Replace the "render every non-hidden attribute" grid with a curated **key-facts** projection:
  an ordered allow-list (`cast`, `provider` → "Where to watch", `network`, genres) mapped to
  labels; multi-valued → chips; anything not on the list is not shown as a raw row.
- Keep humanize/format helpers. Hide internal keys: `_`-prefixed, `type`, `tmdb_id`,
  `_enrich_incomplete` (consumed by the banner, not the grid).
- Meta-line values (`year`, `runtime`, `rating`) are consumed by the title meta line, not
  repeated in key facts.

### `provenance.ts` / `Provenance.tsx`

- `ProvStep.detail` (the technical string) renders inside a nested collapsible "Technical
  details", not inline muted text.
- Summary text comes through as the plain-language sentence from the backend.

---

## Data flow

```
share -> classify(internal) -> extract(vision: primary_subject + roles)
      -> registry.pick(prefer subject_type) -> resolve+enrich(canonical, or merge subject on miss)
      -> categorize(TV Shows aware, collateral excluded) -> dedup -> finalize
      -> item.attributes + _provenance -> detail panel (subject card)
```

## Error handling

- Vision omits `primary_subject` / `role`: defaults keep the pipeline on today's path.
- Enrichment miss: `_enrich_incomplete` reason set, item shows known data + banner, gated to
  `needs_review`.
- No TMDb key: same incomplete path with an explicit reason (no crash, no empty card).
- Unknown `subject_type`: `registry.pick` falls back to `detect()` argmax.

## Testing

Backend (pytest):
- `build_media_item`: TV payload → `category_hints == ["TV Shows"]`, `type == "show"`.
- `registry.pick`: vision `primary_subject.subject_type == "movie"` on an Instagram container
  routes to the movie resolver even when social scores higher on raw signals.
- `subject_entities` helper drops `role:"collateral"` entities.
- `movie.enrich` miss path: returns title + `_enrich_incomplete` reason, low confidence
  (mock TMDb 404 / missing key).
- `describe_resolve` / `describe_vision`: TV phrasing; collateral-ignored phrasing;
  classify step absent from the trace.

Frontend (vitest):
- `attrRows`/key-facts projection: only allow-listed facts render; internal + meta keys hidden.
- Provenance: technical `detail` nested under a toggle, not inline.
- Item page: `_enrich_incomplete` renders the amber banner; hero/title/description still show.

## Rollout

Additive schema (all new fields optional/defaulted) — no migration beyond the seed category.
Existing items keep rendering; re-processing an item picks up the new comprehension + card.
