# PWA Offline Mode + Pending-Sync Panel

Status: approved (design)
Date: 2026-07-12

## Problem

The web PWA (`web/`) currently has no offline behavior beyond whatever the
Android Web Share Target service worker (`sw-share-target.ts`) does for the
share intent itself. Every read (`GET /api/items`, `/categories`, etc.) and
write (ingest, approve/reject/remove, category CRUD, settings) is a plain
`fetch` in `web/src/lib/api.ts` that throws on network failure. When the
self-hosted API is unreachable (phone off the LAN, server down, laptop
offline), the app is unusable and any in-flight action is simply lost.

## Goals

- Previously-viewed screens (Inbox, Item, Categories, Search results,
  Settings) stay browsable, read-only, when the server is unreachable.
- Every mutation (capture/ingest, approve/reject/reprocess/remove, category
  create/delete, settings update) queues locally instead of failing, and
  replays automatically on reconnect.
- A nav-bar status pill shows online/offline state and, when there's queued
  work, a breakdown of pending updates by type, with a manual retry and a
  short log of anything that got dropped.

## Non-goals

- No merge UI for conflicts — single-user app, conflicts are rare edge cases;
  resolution is best-effort (see Error taxonomy below), not interactive.
- No SW-level (Workbox runtime-caching) response caching — see Architecture.
- No offline support for the Android Web Share Target path itself
  (`sw-share-target.ts`) beyond what it already does; that SW intercepts a
  browser-level share intent outside the React app and is out of scope here.

## Architecture

```
web/src/lib/
  offlineDb.ts       IndexedDB (via the `idb` package) — two object stores:
                       `cache` (GET responses, keyed by request URL, value
                       {data, cachedAt}) and `queue` (pending mutations,
                       autoincrement id, FIFO, value {id, type, payload,
                       createdAt, attempts}).
  connectivity.ts    Online/offline detection. Polls `GET /api/health`
                       (already exists, unauthenticated) every ~12s with a
                       4s timeout; also fires an immediate re-ping right
                       after any fetch in the app fails with a network
                       error. Exposes `isOnline()` and `subscribe(cb)`.
  offlineQueue.ts    `enqueue(type, payload)`, `listCounts()` (grouped by
                       type), `recentIssues()` (bounded log, last ~20), and
                       `replay()` — walks the queue FIFO on reconnect or
                       manual retry (see Error taxonomy).
  api.ts (modified)  GET methods: try network; on success, write-through to
                       the `cache` store; on network failure, fall back to
                       the last cached value for that URL, tagged `stale:
                       true`. HTTP error responses (401/500/etc.) still
                       throw as today — only network-level failures (no
                       response at all) trigger the cache fallback.
                     Mutation methods: try network; on network failure,
                       call `offlineQueue.enqueue()` with a type tag
                       (`capture`, `approve`, `reject`, `reprocess`,
                       `remove`, `category_create`, `category_delete`,
                       `settings_update`) and the request payload, apply an
                       optimistic local patch (below), and resolve instead
                       of throwing.
web/src/components/
  SyncStatusPill.tsx  Nav-bar indicator + expandable panel (counts by type,
                       "Retry now", recent issues). Backed by
                       `useOnlineStatus()` / `useQueueCounts()` hooks.
```

**Why app-code IndexedDB instead of a Workbox runtime-caching strategy:**
runtime-caching strategies only apply to the built, registered service
worker — they don't run under `vite dev`, which is where most iteration
happens. Keeping cache + queue logic together in plain TS that runs in the
page context works identically in dev and prod, and it's the same place the
queue/replay logic already needs to live.

## Data flow

**Capture (ingest) offline.** `ingestJSON`/`ingestForm` hits a network
error → enqueue `type: "capture"` with the request payload (plain fields,
plus the image `File`/Blob for form captures — IndexedDB stores Blobs
natively) → return a synthetic `{id: "local:<queueId>", _pending: true}` to
the caller. The Inbox page renders this merged into the real item list as a
"queued" placeholder card (no thumbnail/enrichment yet, just the raw
text/URL and a queued badge). On successful replay, the placeholder is
removed (matched by queue id) and the real item appears via the normal
cache refresh / SSE update.

**Item actions offline** (approve / reject / reprocess / remove). Network
failure → enqueue `type` + item id → apply an optimistic patch directly to
the cached item and any cached list entries containing it (e.g. status
flips to `approved` locally, or the item is removed from cached lists for
`remove`) so the UI reflects the action immediately. Replay performs the
real call later.

**Category create/delete, settings update.** Same optimistic-patch-then-
enqueue pattern against the `categories`/`tree`/`settings` cache entries.

**Replay (`offlineQueue.replay()`)**, triggered when connectivity flips
online or via manual "Retry now": walks the queue FIFO across all types (not
per-type — chronological order matters, e.g. approve-then-remove of the same
item), one entry at a time, per the error taxonomy below.

## Error taxonomy (replay)

| Outcome | Action |
|---|---|
| Success | Dequeue entry, continue to next. |
| Network error (no response) | Stop the whole replay round — we're not actually online. Leave the queue untouched; next attempt fires on the next reconnect or manual retry. |
| `401` | Stop the whole round. Leave the queue untouched (this is real, unsynced work, not a conflict). Surface a distinct "sync paused — check token in Settings" state, separate from the normal offline pill. |
| `5xx` | Stop this round (transient server issue), don't drop the entry. Retry next cycle. |
| `4xx` conflict (`404`/`409`/`410`, etc.) | Drop just this entry — it's stale by definition (e.g. approving an item already deleted elsewhere). Append a one-line note to the bounded "recent issues" log. Continue to the next entry. |

This is the "best-effort, last-write-wins" behavior: queued work is replayed
in order, genuinely stale entries are silently dropped (with a visible
note), and anything ambiguous (auth, transient server errors) is left queued
rather than discarded.

## UI

`SyncStatusPill` sits in the nav bar (`App.tsx`), next to the existing tabs.

- **Online, empty queue** — small green dot, no text.
- **Online, replaying** — spinner while `replay()` is in flight.
- **Offline** — amber/red pill: "Offline" + pending count badge.
- **Sync paused (401)** — distinct pill state pointing at Settings.

Click expands a panel: counts per type (`2 captures · 1 approve · 1
delete`), a "Retry now" button (useful right after reconnecting, before the
next health-ping fires), and the last few recent-issues one-liners (e.g.
`approve "Foo" — item no longer exists, skipped`).

`useOnlineStatus()` / `useQueueCounts()` are small hooks over
`connectivity.ts` / `offlineQueue.ts` so other pages can react later if
needed (e.g. visibly disabling a "Reprocess" button instead of letting it
silently queue) — not built now, just not precluded.

## Testing

`web/` has no test script yet. This feature adds a minimal Vitest setup
scoped to the pure logic:

- `offlineQueue`: enqueue → `listCounts()` correct; replay success dequeues;
  network error stops & preserves queue; `401` pauses & preserves queue;
  `4xx` conflict drops entry + logs an issue; `5xx` stops the round without
  dropping.
- Capture placeholder is removed once its queue entry replays successfully.

UI/integration (`SyncStatusPill`, optimistic patches, Inbox placeholder
rendering) is verified manually: Chrome DevTools "Offline" throttle, capture
a URL, approve/reject an item, flip back online, confirm the pill count
drains and the placeholder resolves into the real card.

**Edge cases in scope:** queue surviving a page reload (IndexedDB persists,
unlike in-memory state); item detail pages stay openable offline for any
item that appeared in a previously-cached list (the list cache backfills
each item's individual detail-cache entry, not just the list itself).
**Explicitly not handled:** duplicate-capture guarding — server-side dedup
(embedding similarity, already implemented) covers it once a queued capture
actually lands. **Dropped during implementation:** a separate per-screen
"stale data" indicator — the nav-bar online/offline pill already tells you
when you're looking at cached data (if it says "Offline", everything on
screen is cache-fallback), so a second indicator would be redundant.
