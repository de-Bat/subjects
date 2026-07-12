# Subjects

Self-hosted, single-user AI capture. Share anything — a URL, a screenshot, a
selection, a note — and get back a **typed, enriched, auto-filed item**. A GitHub
link becomes a repo card with stars, topics and language; a movie screenshot
becomes a film with poster, year, cast and external IDs; anything unrecognized
still gets a sensible generic card via a vision model + readability.

Built per [`CAPTURE_APP_FABLE5_SPEC.md`](CAPTURE_APP_FABLE5_SPEC.md).

## Documentation

- [Getting Started](GETTING_STARTED.md) — install + first capture in ~10 min.
- [User Manual](USER_MANUAL.md) — every screen, capture channel, and workflow.
- [Deployment](DEPLOYMENT.md) — topology, config reference, backups, HTTPS, ops.
- [Spec](CAPTURE_APP_FABLE5_SPEC.md) — the original v1 specification.

> All docs live in this `docs/` folder. Paths below are relative to the repo
> root (one level up).

---

## Architecture

```
web/         React 18 + TS + Vite PWA (Tailwind). Inbox, Item, Categories, Review, Search, Settings.
extension/   MV3 browser extension — "Send to Subjects" toolbar button + right-click menu.
api/         FastAPI + Uvicorn (async SQLAlchemy / asyncpg, Pydantic v2).
             ├─ POST /api/ingest        single ingestion endpoint (stub + enqueue, 201 fast)
             ├─ /api/items, /api/categories, /api/search, /api/settings
             ├─ /api/events             SSE stream (Postgres LISTEN/NOTIFY → browser)
             ├─ pipeline/               classify → extract → resolve → enrich → categorize → dedup → finalize
             └─ resolvers/              github, movie, youtube, paper, recipe, product, article, social, generic
worker       procrastinate worker draining the Postgres job queue (no Redis).
postgres     Postgres 16 + pgvector (items, taxonomy, embeddings, job queue).
meilisearch  Full-text index (Phase 4).
ollama       External LLM/VLM provider (default, local): Qwen2.5-VL 7B vision + nomic-embed-text.
             Swap in openai or nim (NVIDIA NIM) via AI_PROVIDER — see Configuration below.
```

Ingestion channels (all thin clients of `POST /api/ingest`):
**Android** Web Share Target (PWA) · **iOS** Shortcut (Appendix A below) ·
**Desktop** in-app paste + drag-drop · **Browser** MV3 extension.

---

## Requirements

- Docker + Docker Compose.
- An LLM provider. Default is a **separate Ollama** instance reachable from the
  API container (`OLLAMA_BASE_URL`) — fully local. Alternatively set
  `AI_PROVIDER=openai` with an API key, or `AI_PROVIDER=nim` with a
  `NIM_API_KEY` to use NVIDIA NIM (self-hosted microservice or
  `build.nvidia.com`). Ollama is intentionally **not** in the compose file — run
  it on the host or another box where the model weights and (ideally) a GPU live.

## Setup

```bash
cp .env.example .env
# edit .env: set APP_TOKEN, OLLAMA_BASE_URL (or AI_PROVIDER=openai + OPENAI_API_KEY,
# or AI_PROVIDER=nim + NIM_API_KEY), optional TMDB_API_KEY / GITHUB_TOKEN for the
# flagship resolvers.

docker compose up --build
```

- Web UI: <http://localhost:8080>
- API: <http://localhost:8000> (the web container reverse-proxies `/api`, so
  leave the Settings "API base URL" blank when using the app on `:8080`)

On first boot the API applies the schema and seeds the base taxonomy. Open the
web app → **Settings** → set the **API base URL** and paste your `APP_TOKEN`
(stored per-device in `localStorage`). Then paste a URL into the Inbox and watch
it enrich live.

### Ollama models

```bash
ollama pull qwen2.5-vl:7b        # vision + text
ollama pull nomic-embed-text     # embeddings (dedup + semantic search)
```

Change models later without a redeploy in **Settings** (persisted in the DB).

---

## Using it

- **Inbox** — paste a URL/text, or drag/paste an image. Items appear as a
  `pending` stub and update live (SSE) to `enriched` or `needs_review`.
- **Categories** — browse the auto-filed tree; one item can sit under several
  categories (a repo files under both *Development* and *Links*).
- **Review** — low-confidence / ambiguous captures land here instead of being
  silently mis-filed. Approve or reject.
- **Search** — full-text (Meilisearch, with a SQL fallback) or semantic
  (pgvector embeddings).

---

## Appendix A — iOS Shortcut ("Send to Subjects")

iOS PWAs cannot register a Web Share Target, so use a Shortcut as the receive path:

1. **Shortcuts app → new Shortcut →** enable **"Show in Share Sheet"**; accept
   Images, URLs, and Text.
2. Add action **Get Contents of URL**:
   - URL: `https://<your-host>:8000/api/ingest`
   - Method: `POST`
   - Header: `Authorization` = `Bearer <APP_TOKEN>`
3. Request Body: **Form**. Add the **Shortcut Input** as field `media` for images,
   or as `url` / `text` for links and notes.
4. Name it **"Send to Subjects."** It now appears in the iOS share sheet.

## Browser extension

1. `chrome://extensions` → enable **Developer mode** → **Load unpacked** →
   select the `extension/` folder (works in Chrome/Edge; Firefox via
   `about:debugging`).
2. Open the extension **Options**, set the **API base URL** and **token**, and
   optionally enable **screenshot capture**.
3. Click the toolbar button or right-click → **Send to Subjects** on any page,
   selection, link, or image.

---

## Adding a new resolver

A resolver is a plugin that recognizes an entity type and returns typed data.
Contract lives in [`api/app/resolvers/base.py`](../api/app/resolvers/base.py):

1. Subclass `Resolver`, set `id`, `item_type`, and `category_hints`.
2. Implement `detect(signals) -> float` (0..1 confidence this resolver applies)
   and `async enrich(signals) -> EnrichedItem`.
3. Register the instance in
   [`api/app/resolvers/registry.py`](../api/app/resolvers/registry.py)
   (`_load_defaults`). Nothing else.

The registry runs every `detect()`, picks the argmax above `MIN_DETECT` (0.5),
and falls back to `generic` otherwise. Use the existing `github` /`movie`
resolvers as templates for the API-call + LLM-disambiguation pattern.

```python
class HackerNewsResolver(Resolver):
    id = "hackernews"
    item_type = "discussion"
    category_hints = ["Links", "Reading"]

    def detect(self, signals: Signals) -> float:
        return 0.9 if signals.url and "news.ycombinator.com" in signals.url else 0.0

    async def enrich(self, signals: Signals) -> EnrichedItem:
        ...
```

---

## Configuration

See [`.env.example`](../.env.example) for every variable. Key ones:

| Var | Meaning |
|-----|---------|
| `APP_TOKEN` | Bearer token every write channel must send. |
| `AI_PROVIDER` | `ollama` (default, local), `openai`, or `nim`. |
| `OLLAMA_BASE_URL` | URL of your external Ollama. |
| `OPENAI_API_KEY` | Required when `AI_PROVIDER=openai`. |
| `NIM_API_KEY` / `NIM_BASE_URL` | Required when `AI_PROVIDER=nim` — NVIDIA NIM, self-hosted or `build.nvidia.com`. |
| `CONFIDENCE_AUTO` | Auto-accept threshold (default `0.8`); below → `needs_review`. |
| `TMDB_API_KEY` | Enables the movie resolver. |
| `GITHUB_TOKEN` | Higher rate limit for the github resolver (optional). |

## Development

```bash
# API
cd api && python -m venv .venv && . .venv/bin/activate && pip install -e .
uvicorn app.main:app --reload

# Web
cd web && npm install && npm run dev
```

## Notes / v1 non-goals

Single-user (one shared token, no multi-tenant auth); no mobile-native apps
(PWA + Shortcut instead); Ollama runs outside compose.
