# Getting Started

Get **Subjects** running and capture your first item in ~10 minutes. For a
deeper operational guide see [DEPLOYMENT.md](DEPLOYMENT.md); for day-to-day use
see the [USER_MANUAL.md](USER_MANUAL.md).

---

## What you're setting up

Five containers via Docker Compose — `web`, `api`, `worker`, `postgres`,
`meilisearch` — plus an LLM/VLM provider: **Ollama** (default, local, run
yourself outside compose, ideally on a machine with a GPU), or a hosted/self-hosted
alternative — **OpenAI-compatible** or **NVIDIA NIM**.

```
Browser / phone ──▶ web (nginx :8080) ──/api──▶ api (FastAPI :8000) ──▶ postgres (pgvector)
                                                    │                        ▲
                                                    ├── enqueue job ─────────┘
                                                    ▼
                                              worker (pipeline) ──▶ ollama (local :11434)
                                                                └──▶ openai / nim (hosted)
                                                                └──▶ meilisearch (search)
```

---

## Prerequisites

| Need | Why |
|------|-----|
| Docker + Docker Compose v2 | Runs the whole stack. |
| An LLM provider | **Ollama** (default, local) **or** an OpenAI-compatible key **or** an NVIDIA NIM key. |
| ~8 GB free RAM / a GPU (recommended) | The 7B vision model is the heavy part. |

### Install Ollama + models (default path)

On the host (or any box reachable from the API container):

```bash
# https://ollama.com/download
ollama pull qwen2.5-vl:7b       # vision + text
ollama pull nomic-embed-text    # embeddings (dedup + semantic search)
ollama serve                    # listens on :11434
```

Prefer OpenAI instead? Skip Ollama and set `AI_PROVIDER=openai` + `OPENAI_API_KEY`
in `.env` (below). Prefer NVIDIA NIM? Set `AI_PROVIDER=nim` + `NIM_API_KEY` (and
`NIM_BASE_URL` if self-hosting the microservice instead of `build.nvidia.com`).

---

## 1. Configure

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```ini
APP_TOKEN=<a-long-random-string>          # the shared bearer token
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434   # host Ollama, from inside a container
```

Optional but recommended to unlock the flagship flows:

```ini
TMDB_API_KEY=<your-tmdb-key>   # enables the movie resolver
GITHUB_TOKEN=<a-pat>           # higher GitHub rate limit
```

> `host.docker.internal` resolves to your host from inside the containers — the
> compose file already wires the `extra_hosts` entry for Linux.

---

## 2. Launch

```bash
docker compose up --build
```

First boot: the API applies the schema and seeds the base taxonomy
(*Development, Links, Movies, Articles, Products, Recipes, Papers, Social, Inbox*).

- **Web app:** <http://localhost:8080>
- **API:** <http://localhost:8000>

---

## 3. Connect the app

Open <http://localhost:8080> → **Settings**:

- **API base URL:** leave **blank** (the web container reverse-proxies `/api` to
  the API, same origin). Only fill it when the app talks to the API cross-origin
  (e.g. the extension or a phone → `http://<host-ip>:8000`).
- **Bearer token:** paste your `APP_TOKEN`.

Click **Save connection**.

---

## 4. Capture your first item

Go to **Inbox** and paste a URL, e.g.:

```
https://github.com/tiangolo/fastapi
```

You should see:

1. A `pending` stub appears immediately (the API returns 201 without waiting).
2. Within seconds it flips live (via SSE) to `enriched` — a GitHub repo card with
   the avatar icon, star count, topics as tags, and links.

Try a movie screenshot (drag-drop or paste an image) or an article URL to see the
generic + typed resolvers in action.

Check the nav pill (top right) — it shows Online/Offline/Syncing. Lose the
connection and the app keeps working: captures, approvals, category edits,
and settings changes all queue locally and replay once you're back online.
See [USER_MANUAL.md](USER_MANUAL.md#inbox--capture--live-feed) for details.

---

## Troubleshooting quick hits

| Symptom | Fix |
|---------|-----|
| Items stay `pending` forever | The `worker` can't reach the AI provider. Check `OLLAMA_BASE_URL` + `ollama serve` (or `NIM_BASE_URL`/`NIM_API_KEY` for nim). `docker compose logs worker`. |
| `401` on capture | Token in **Settings** ≠ `APP_TOKEN` in `.env`. |
| Everything lands in **Review** | Confidence below `CONFIDENCE_AUTO` (0.8). Model too small / prompts need tuning, or genuinely ambiguous input. |
| Search returns nothing | Meilisearch still indexing, or down — it falls back to SQL `ILIKE`. Check `docker compose logs meilisearch`. |

Full runbook: [DEPLOYMENT.md](DEPLOYMENT.md#troubleshooting).
