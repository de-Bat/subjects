# Progress Log

## Session 1 — 2026-07-12
- Read spec, created planning files.
- Toolchain: python 3.12.10, node 24.15, npm 11.12, git present. NO docker, NO local postgres.
- Backend built: config, db+schema, ORM+schemas, ai provider (ollama/openai), prompts, vision, embeddings,
  9 resolvers (github/movie/youtube/paper/recipe/product/article/social/generic), registry,
  pipeline stages (classify/extract/resolve/enrich/categorize/dedup/run), jobs (procrastinate), worker,
  API routers (ingest/items/categories/events-SSE/search/settings), main.py, search service, runtime_settings.
- CONSTRAINT: no docker/postgres/ollama here → full E2E exit criteria not runnable in this env;
  verified via py compileall + vite build + documented runtime requirements.

## Session 2 — 2026-07-12 (continue)
- Frontend complete: StatusBadge + 6 pages (Inbox, Item, Category, Review, Search, Settings)
  wired to api.ts/sse.ts. Inbox = paste/drag/paste-image capture + live SSE updates.
- BUG FIX: web ingestForm sent form field `file`; ingest endpoint expects `media`. Fixed Inbox.
- MV3 extension built: manifest, background.js (toolbar + right-click "Send to Subjects",
  URL/selection/optional screenshot → POST /api/ingest), options.html/js (apiBase+token+screenshot).
- Placeholder icons generated (extension/icon-128, web/public/icon-192+512) via Pillow.
- web/Dockerfile (node build → nginx) + nginx.conf (SPA fallback, /api proxy, /api/events SSE no-buffer).
- README.md: architecture, docker setup, Ollama models, iOS Shortcut (Appendix A), extension load,
  how to add a resolver, config table, dev commands.
- BUG FIX: vite.config PWA injectManifest had stray swSrc/swDest → build ENOENT sw.js. Removed; build clean.
- VERIFY PASS: `python -m compileall api/app` OK; `cd web && npm install && npm run build` OK
  (tsc typecheck + vite + PWA injectManifest, dist/sw-share-target.js generated).
- REMAINING (needs live runtime — cannot run here): `docker compose up` E2E, flagship github/movie
  flows against real TMDb/GitHub + Ollama, Android share-target from a phone, dedup/search exit criteria.
- DOCS: wrote GETTING_STARTED.md, USER_MANUAL.md, DEPLOYMENT.md. Moved ALL .md (README, findings,
  progress, task_plan) into docs/ — root has no .md now. Fixed README relative links (../api, ../.env)
  + added docs index. FIX: real token env var is APP_TOKEN (was mis-documented as SUBJECTS_TOKEN in
  README + Settings.tsx placeholder).
