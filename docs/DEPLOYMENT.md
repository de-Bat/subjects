# Deployment

Operational guide for running **Subjects** as a self-hosted, single-user service.
For a first run use [GETTING_STARTED.md](GETTING_STARTED.md).

---

## Topology

```
                         docker compose
  ┌──────────────────────────────────────────────────────────┐
  │  web   nginx :80  (host :8080)  ── serves PWA, proxies /api │
  │  api   uvicorn :8000 (host :8000)  ── FastAPI               │
  │  worker  python -m app.worker      ── procrastinate queue   │
  │  postgres  pgvector/pg16  (volume pgdata)                   │
  │  meilisearch  v1.9        (volume meilidata)                │
  │  (appdata volume mounted in api + worker → /data media)     │
  └──────────────────────────────────────────────────────────┘
                         │ OLLAMA_BASE_URL
                         ▼
            Ollama  :11434   (EXTERNAL — you run this)
```

- **web** and **worker** both build from `./api` (worker just runs a different
  command). `web` builds from `./web` (node build → nginx).
- **Ollama is not in compose** — run it on the host or another box. The API/worker
  reach it via `OLLAMA_BASE_URL` (default `http://host.docker.internal:11434`;
  compose wires `host.docker.internal` for Linux via `extra_hosts`).

### Ports

| Service | Container | Host | Notes |
|---------|-----------|------|-------|
| web | 80 | **8080** | Primary entrypoint; reverse-proxies `/api` + SSE. |
| api | 8000 | **8000** | Direct API access (extension, phone, Shortcut). |
| postgres | 5432 | — | Internal only. |
| meilisearch | 7700 | — | Internal only. |

---

## Configuration reference (`.env`)

| Var | Default | Purpose |
|-----|---------|---------|
| `APP_TOKEN` | `change-me-…` | **Shared bearer token.** Required on every write. Set to a long random string. |
| `DATABASE_URL` | `postgresql+asyncpg://…` | Async SQLAlchemy DSN (app). |
| `DATABASE_DSN` | `postgresql://…` | Plain psycopg DSN (procrastinate + LISTEN/NOTIFY). |
| `POSTGRES_USER/PASSWORD/DB` | `subjects` | Postgres credentials. |
| `AI_PROVIDER` | `ollama` | `ollama` or `openai`. |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | External Ollama. |
| `VISION_MODEL` | `qwen2.5vl:7b` | VLM for image/OCR path. |
| `TEXT_MODEL` | `qwen2.5vl:7b` | Text LLM (classify/disambiguate/categorize). |
| `EMBED_MODEL` | `nomic-embed-text` | Embeddings (dedup + semantic search). |
| `EMBED_DIM` | `768` | Embedding vector dimension (must match model). |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | — | Used when `AI_PROVIDER=openai`. |
| `OPENAI_VISION/TEXT/EMBED_MODEL` | `gpt-4o-mini` / `…-3-small` | OpenAI model slots. |
| `GITHUB_TOKEN` | — | Higher GitHub API rate limit (optional). |
| `TMDB_API_KEY` | — | Enables the movie resolver. |
| `CONFIDENCE_AUTO` | `0.8` | Auto-file threshold; below → `needs_review`. |
| `DEDUP_THRESHOLD` | `0.90` | Embedding similarity to treat as duplicate. |
| `MEILI_URL` | `http://meilisearch:7700` | Search service. |
| `MEILI_MASTER_KEY` | `change-me-…` | Set a real key in production. |
| `DATA_DIR` | `/data` | Media (uploaded screenshots) storage. |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Base URL clients/phones use for media links. |

`vision_model`, `text_model`, `embed_model`, `confidence_auto`, `dedup_threshold`
are also **runtime-editable in Settings** (stored in the DB, override env, no
redeploy). Everything else is env-only.

---

## Provider options

### Ollama (default, private)

```bash
ollama pull qwen2.5-vl:7b
ollama pull nomic-embed-text
ollama serve                 # :11434
```

Run it where the GPU is. If Ollama is on another host, set
`OLLAMA_BASE_URL=http://<that-host>:11434` and ensure the port is reachable from
the containers.

### OpenAI-compatible

```ini
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1   # or any compatible gateway
```

Data leaves your network in this mode — choose deliberately.

---

## Remote / phone access & HTTPS

The Android share target and iOS Shortcut need the API reachable from the phone,
and **Web Share Target / installable PWA require HTTPS** (except on `localhost`).

Recommended: put a TLS-terminating reverse proxy (Caddy, nginx, Traefik) in front:

```
# Caddyfile
subjects.example.com {
    reverse_proxy localhost:8080
}
```

Then set `PUBLIC_BASE_URL=https://subjects.example.com` so media links resolve,
and point the extension / Shortcut / phone at `https://subjects.example.com`.
On a pure LAN, use the host IP (`http://192.168.x.x:8080`) — PWA install won't
work over plain HTTP off `localhost`, but capture still does.

---

## Data, volumes & backups

| Volume | Holds | Back up? |
|--------|-------|----------|
| `pgdata` | Postgres: items, taxonomy, embeddings, **job queue** | **Yes — this is your data.** |
| `appdata` | Uploaded media (screenshots) under `/data/media` | Yes if you value the images. |
| `meilidata` | Search index (rebuildable) | Optional — can be reindexed. |

Backup Postgres:

```bash
docker compose exec postgres pg_dump -U subjects subjects > backup.sql
```

Restore into a fresh DB with `psql`. Media is just files in the `appdata` volume —
copy it with `docker run --rm -v subjects_appdata:/d -v $PWD:/out alpine tar czf /out/media.tgz -C /d .`.

---

## Operations

### Logs / status

```bash
docker compose ps
docker compose logs -f worker      # pipeline activity
docker compose logs -f api
```

### Update to a new version

```bash
git pull
docker compose build
docker compose up -d
```

Schema migrations + taxonomy seed run automatically on API start (idempotent).

### Scale the worker

The pipeline is a Postgres-backed `procrastinate` queue (no Redis). Run more
drainers for throughput:

```bash
docker compose up -d --scale worker=3
```

### Reprocess after a model/key change

Change the model in **Settings** (or add `TMDB_API_KEY`), then open affected items
and hit **Reprocess** — or re-capture.

---

## Security notes

- **Single-user by design.** Auth is one static bearer token (`APP_TOKEN`) checked
  on every write. There is no multi-tenant login. Treat the token like a password;
  rotate it by changing `.env` and restarting.
- **Media reads are public** (`GET /api/media/{name}`) so thumbnails render without
  auth — the write guard is on ingest. Don't expose the raw API to the internet
  without the reverse proxy + TLS above.
- Set real values for `APP_TOKEN` and `MEILI_MASTER_KEY` before any non-local
  deployment. The defaults are placeholders.

---

## Troubleshooting

| Symptom | Cause → Fix |
|---------|-------------|
| Items stuck `pending` | Worker can't reach Ollama, or no worker running. `docker compose logs worker`; verify `OLLAMA_BASE_URL` + `ollama serve`. |
| `401 Unauthorized` on capture | Client token ≠ `APP_TOKEN`. Re-enter in Settings / extension Options / Shortcut header. |
| Live updates never arrive | SSE blocked by a proxy buffering `/api/events`. The bundled nginx disables buffering; a custom proxy must too (`proxy_buffering off`). |
| Everything → `needs_review` | Model too weak or input ambiguous. Lower `confidence_auto`, or use a stronger model. |
| Movie/GitHub items stay generic | Missing `TMDB_API_KEY` / rate-limited GitHub. Add keys, Reprocess. |
| Search empty | Meilisearch down/indexing → SQL fallback active. `docker compose logs meilisearch`; check `MEILI_URL`/`MEILI_MASTER_KEY`. |
| Embeddings/dedup/semantic off | `EMBED_MODEL` not pulled, or `EMBED_DIM` mismatch with the model. |
| PWA won't install on phone | Needs HTTPS off `localhost`. Add the reverse proxy + TLS. |
