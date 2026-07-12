# User Manual

How to use **Subjects** day-to-day. New here? Start with
[GETTING_STARTED.md](GETTING_STARTED.md).

---

## Concepts

- **Item** — one captured thing (a repo, a film, an article, a screenshot, a
  note). Has a **type**, a **status**, a title/description/thumbnail, structured
  **attributes**, **links**, **tags**, and **categories**.
- **Resolver** — the plugin that recognized the item and produced its typed data
  (`github`, `movie`, `youtube`, `paper`, `recipe`, `product`, `article`,
  `social`, or `generic`).
- **Category** — where an item is filed. One item can sit in **several**
  categories at once (a repo files under both *Development* and *Links*).
- **Confidence** — the pipeline's certainty. Above `CONFIDENCE_AUTO` (default
  0.8) the item auto-files; below it goes to **Review**.

### Item lifecycle (statuses)

| Status | Meaning |
|--------|---------|
| `pending` | Stub created; queued for processing. |
| `processing` | Worker is enriching it. |
| `enriched` | Fully resolved and auto-filed. |
| `needs_review` | Low confidence / ambiguous — waiting for your call. |
| `duplicate` | Merged into an existing item (hidden from lists). |
| `rejected` | You rejected it in Review. |
| `error` | Processing failed (see item / worker logs). |

Updates stream **live** to the UI over SSE — no refresh needed.

---

## The five screens

### Inbox — capture + live feed

The capture surface and your recent items.

- **Paste a URL or text** into the box → **Capture** (or `Ctrl/⌘+Enter`). A URL
  is fetched and resolved; plain text becomes a note.
- **Drag-drop an image** anywhere on the Inbox, or **paste an image** from the
  clipboard (e.g. a screenshot) → it uploads and runs the vision + OCR path.
- New captures appear instantly as `pending` and update in place as they enrich.

**Offline mode.** If the app can't reach the server (nav pill shows "Offline"),
captures, approvals/rejections, category edits, and settings changes all still
work — they're queued in the browser and replayed automatically once the
connection comes back. Click the nav pill to see what's pending, broken down
by type, and to trigger a manual retry. Anything the server rejects as stale
on replay (e.g. approving an item already deleted elsewhere) is dropped
silently with a one-line note in that same panel — everything else stays
queued until it succeeds.

### Item — the detail view

Click any card. Shows the thumbnail/screenshot, title, canonical URL, description,
**attributes** table, **links**, tags, and categories. Actions:

- **Approve / Reject** — only shown when the item is `needs_review`.
- **Reprocess** — re-run the pipeline (after changing a model or fixing a key).
- **Delete** — remove the item permanently.

### Categories — browse the tree

Left: the category tree with per-category counts (nested children indented).
Click a category to list its items. Categories are seeded on first boot and grow
as the LLM files new items; you can also manage them (see below).

### Review — the safety net

Every item the pipeline wasn't sure about lands here instead of being silently
mis-filed. Each row has inline **Approve** (accept as `enriched`) and **Reject**.
This is the core promise: **low-confidence inputs are never auto-filed wrongly.**

### Search

- **Full-text** — Meilisearch across everything you captured (falls back to a SQL
  `ILIKE` if Meilisearch is down, so it always returns something).
- **Semantic** — pgvector embedding similarity; finds conceptually related items
  even without a keyword match. Requires the embedding model.

Click any hit to open the item.

### Settings

Two groups:

- **Connection (this device)** — API base URL + bearer token, stored per-device
  in `localStorage`. Blank base URL = same origin (use the app on `:8080`).
- **AI / server settings** — persisted in the DB, no redeploy. Editable keys:
  `vision_model`, `text_model`, `embed_model`, `confidence_auto`,
  `dedup_threshold`. A green dot marks a secret that is already set; leave a
  secret field blank to keep the current value.

---

## Capturing from anywhere

Every channel is a thin client of `POST /api/ingest`.

| Channel | How |
|---------|-----|
| **Desktop app** | Paste URL/text, drag-drop or paste an image in the Inbox. |
| **Browser extension** | Toolbar button or right-click **"Send to Subjects"** — sends the page URL + any selection, and (optional) a screenshot. Configure API base + token in the extension **Options**. |
| **Android** | Install the PWA ("Add to Home screen"), then use the system **Share** sheet → Subjects (Web Share Target). |
| **iOS** | Use the **"Send to Subjects" Shortcut** (see below) from the share sheet — iOS PWAs can't be a share target. |

### iOS Shortcut setup

1. Shortcuts app → new Shortcut → enable **"Show in Share Sheet"**; accept
   Images, URLs, Text.
2. Action **Get Contents of URL**:
   - URL `https://<your-host>:8000/api/ingest`
   - Method `POST`, Header `Authorization` = `Bearer <APP_TOKEN>`
3. Body **Form**: Shortcut Input as `media` (images) or `url` / `text`.
4. Name it **"Send to Subjects."**

### Browser extension setup

1. `chrome://extensions` → **Developer mode** → **Load unpacked** → pick the
   `extension/` folder. (Firefox: `about:debugging` → load temporary add-on.)
2. Extension **Options** → set **API base URL** + **token**, optionally enable
   **screenshot capture**.
3. Use the toolbar button or right-click on a page/selection/link/image.

---

## Tips

- **Something mis-typed?** Open the item → **Reprocess** after tuning the model or
  adding an API key (e.g. set `TMDB_API_KEY` to turn movie screenshots into real
  film cards).
- **Duplicates** are detected by embedding similarity (`DEDUP_THRESHOLD`, default
  0.90). Sharing the same repo as a link and as a screenshot collapses to one
  item; the extra is marked `duplicate` and hidden.
- **Too much / too little in Review?** Adjust `confidence_auto` in Settings.
  Higher = stricter (more review); lower = more auto-filing.
- **Multi-filing is intentional.** Don't be surprised to see one item under
  several categories — that's the design.
