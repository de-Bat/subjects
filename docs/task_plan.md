# Task Plan: Implement CAPTURE_APP_FABLE5_SPEC.md ("Subjects")

## Goal
Build v1 single-user self-hosted AI capture app per docs/CAPTURE_APP_FABLE5_SPEC.md.
Definition of done: Phase 0-4 exit criteria pass + compose up works + README documents setup/iOS Shortcut/adding resolvers.

## Locked stack (do NOT deviate)
React18+TS+Vite PWA (Tailwind, vite-plugin-pwa) | Python3.12+FastAPI+Uvicorn (Pydantic v2) |
procrastinate (Postgres queue, NO Redis) | LISTEN/NOTIFY→SSE | Postgres16+pgvector |
Meilisearch (Phase 4) | Ollama default provider (Qwen2.5-VL 7B vision, nomic-embed-text) |
MV3 extension | Docker Compose (web, api, worker, postgres, meilisearch; external Ollama URL)

## Phases

### Phase 0 — Skeleton [pending]
- [ ] Repo layout (Section 3), docker-compose.yml, .env.example
- [ ] api: config, db (async SQLAlchemy/asyncpg), models, migrations + seed taxonomy
- [ ] POST /api/ingest (URL → sync OG/JSON-LD fetch → item)
- [ ] Minimal React app: list items, item view
- Exit: paste URL in UI → item with title/description/thumbnail

### Phase 1 — Ingestion channels [pending]
- [ ] Ingest → stub + enqueue (return 201 fast)
- [ ] Android Web Share Target (manifest + SW forwarder)
- [ ] Desktop paste + drag-drop
- [ ] Minimal MV3 extension
- [ ] iOS Shortcut doc (Appendix A → README)
- Exit: item creatable from all 4 channels, fast 201, pending stub visible

### Phase 2 — Async pipeline + generic resolver [pending]
- [ ] procrastinate worker + stage chain (classify→extract→resolve→enrich→categorize→dedup→finalize)
- [ ] SSE /api/events wired to UI (LISTEN/NOTIFY)
- [ ] generic resolver: VLM+OCR image path, OG/JSON-LD/readability URL path, text path
- [ ] Confidence gating, needs_review, Review page
- Exit: screenshot/article URL → pending → live update to enriched/needs_review

### Phase 3 — Typed resolvers [pending]
- [ ] Resolver registry detect/enrich routing
- [ ] github resolver (REST API, avatar icon, stars, topics→tags)
- [ ] movie resolver (TMDb search + LLM disambiguation + videos + external IDs)
- Exit: both Section 1 flagship flows work; ambiguous input → needs_review

### Phase 4 — Categorize/dedup/search [pending]
- [ ] LLM categorization → multi item_categories + tags
- [ ] pgvector embedding dedup (merge/link)
- [ ] Meilisearch indexing + search box + category tree UI
- Exit: repo files under Development+Links; link+screenshot dedup to one; FTS finds it

### Phase 5 — Breadth (optional beyond DoD) [pending]
- [ ] More resolvers (article/product/recipe/paper/youtube/social)
- [ ] Settings page (models, keys, taxonomy editing)
- [ ] Semantic search, review-queue UX polish

## Key decisions
- Repo root = C:\web.projects\subjects (not nested capture-app/)
- Follow Section 3 layout exactly: api/, web/, extension/
- Confidence CONFIDENCE_AUTO=0.8 default
- Single migration SQL + seed on startup (no alembic churn for v1)

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
