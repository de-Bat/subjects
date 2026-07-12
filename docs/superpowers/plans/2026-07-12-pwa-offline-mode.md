# PWA Offline Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `web/` PWA browsable offline (cached reads) and queue every mutation (capture, item actions, category CRUD, settings) in IndexedDB for automatic replay on reconnect, with a nav-bar pill showing pending counts by type.

**Architecture:** All new logic lives under `web/src/lib/` as small focused modules (`offlineDb.ts` for IndexedDB access, `connectivity.ts` for online/offline detection, `offlineQueue.ts` for the mutation queue + replay), consumed by `web/src/lib/api.ts` (wraps every GET with a cache-fallback and every mutation with an enqueue-on-network-failure path) and a new `SyncStatusPill` nav component. No Workbox/service-worker runtime caching — this is plain application code, so it behaves identically under `vite dev` and the built PWA.

**Tech Stack:** React 18 + TS (existing), `idb` (IndexedDB wrapper), Vitest + `fake-indexeddb` + `jsdom` (new test harness — none exists yet in `web/`).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-12-pwa-offline-mode-design.md` — every task below implements one section of it; do not deviate from the error taxonomy or module boundaries defined there without checking back.
- `web/tsconfig.json` has `strict: true`, `noUnusedLocals: true`, `noUnusedParameters: true` — all new code must satisfy this (no unused imports/vars).
- Only network-level failures (fetch's promise rejecting — `TypeError` in browsers) trigger cache-fallback / enqueue behavior. A resolved-but-non-2xx HTTP response must keep throwing exactly as it does today (existing `handle<T>()` behavior unchanged for the online path).
- Existing exported names/signatures in `web/src/lib/api.ts` (the `api` object's methods, `Item`, `Category`, `TreeNode`, `SettingsPayload` types, `getToken`/`setToken`/`getApiBase`/`setApiBase`, `mediaUrl`) must not change shape — only their internals.

---

### Task 1: Test harness + `idb` dependency

**Files:**
- Modify: `web/package.json`
- Create: `web/vitest.config.ts`
- Create: `web/vitest.setup.ts`
- Create: `web/src/lib/smoke.test.ts`

**Interfaces:**
- Produces: a working `npm test` (via `vitest run`) that all later tasks' test files rely on. `fake-indexeddb/auto` is globally imported via `vitest.setup.ts` so every test file gets a working `indexedDB` global without re-importing it.

- [ ] **Step 1: Install dependencies**

Run:
```bash
cd web && npm install idb && npm install -D vitest jsdom fake-indexeddb
```

- [ ] **Step 2: Add the test script**

In `web/package.json`, add to `"scripts"`:

```json
"test": "vitest run"
```

(Full `scripts` block becomes:)
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "test": "vitest run"
},
```

- [ ] **Step 3: Write the Vitest config**

Create `web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
  },
});
```

- [ ] **Step 4: Write the global test setup**

Create `web/vitest.setup.ts`:
```ts
import "fake-indexeddb/auto";
```

- [ ] **Step 5: Write a smoke test**

Create `web/src/lib/smoke.test.ts`:
```ts
import { describe, expect, it } from "vitest";

describe("test harness", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 6: Run it**

Run: `cd web && npm test`
Expected: `1 passed`, exit code 0.

- [ ] **Step 7: Commit**

```bash
cd web && git add package.json package-lock.json vitest.config.ts vitest.setup.ts src/lib/smoke.test.ts
git commit -m "test: add vitest harness for offline-mode work"
```

---

### Task 2: `offlineDb.ts` — IndexedDB cache + queue stores

**Files:**
- Create: `web/src/lib/offlineDb.ts`
- Test: `web/src/lib/offlineDb.test.ts`

**Interfaces:**
- Produces:
  - `type QueueType = "capture" | "approve" | "reject" | "reprocess" | "remove" | "category_create" | "category_delete" | "settings_update"`
  - `interface CacheEntry { data: unknown; cachedAt: number }`
  - `interface QueueEntry { id: number; type: QueueType; payload: unknown; createdAt: number }`
  - `cacheGet(key: string): Promise<CacheEntry | undefined>`
  - `cacheSet(key: string, data: unknown): Promise<void>`
  - `cacheEntries(): Promise<Array<[string, CacheEntry]>>`
  - `queueAdd(type: QueueType, payload: unknown): Promise<number>`
  - `queueAll(): Promise<QueueEntry[]>`
  - `queueDelete(id: number): Promise<void>`
  - `_resetDbHandle(): void` (test-only)

- [ ] **Step 1: Write the failing tests**

Create `web/src/lib/offlineDb.test.ts`:
```ts
import { beforeEach, describe, expect, it } from "vitest";
import { cacheGet, cacheSet, queueAdd, queueAll, queueDelete, _resetDbHandle } from "./offlineDb";

async function wipe(): Promise<void> {
  _resetDbHandle();
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.deleteDatabase("subjects-offline");
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    req.onblocked = () => resolve();
  });
}

beforeEach(wipe);

describe("offlineDb cache store", () => {
  it("returns undefined for a missing key", async () => {
    expect(await cacheGet("nope")).toBeUndefined();
  });

  it("round-trips a value", async () => {
    await cacheSet("/api/items", [{ id: "1" }]);
    const entry = await cacheGet("/api/items");
    expect(entry?.data).toEqual([{ id: "1" }]);
    expect(typeof entry?.cachedAt).toBe("number");
  });
});

describe("offlineDb queue store", () => {
  it("adds entries in FIFO order with autoincrement ids", async () => {
    const id1 = await queueAdd("approve", { id: "a" });
    const id2 = await queueAdd("reject", { id: "b" });
    expect(id2).toBeGreaterThan(id1);

    const all = await queueAll();
    expect(all.map((e) => e.type)).toEqual(["approve", "reject"]);
  });

  it("deletes an entry by id", async () => {
    const id = await queueAdd("remove", { id: "x" });
    await queueDelete(id);
    expect(await queueAll()).toEqual([]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/offlineDb.test.ts`
Expected: FAIL — `Cannot find module './offlineDb'`.

- [ ] **Step 3: Implement `offlineDb.ts`**

Create `web/src/lib/offlineDb.ts`:
```ts
import { openDB, type IDBPDatabase } from "idb";

export type QueueType =
  | "capture"
  | "approve"
  | "reject"
  | "reprocess"
  | "remove"
  | "category_create"
  | "category_delete"
  | "settings_update";

export interface CacheEntry {
  data: unknown;
  cachedAt: number;
}

export interface QueueEntry {
  id: number;
  type: QueueType;
  payload: unknown;
  createdAt: number;
}

const DB_NAME = "subjects-offline";
const DB_VERSION = 1;
const CACHE_STORE = "cache";
const QUEUE_STORE = "queue";

let dbPromise: Promise<IDBPDatabase> | null = null;

function getDb(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(CACHE_STORE)) {
          db.createObjectStore(CACHE_STORE);
        }
        if (!db.objectStoreNames.contains(QUEUE_STORE)) {
          db.createObjectStore(QUEUE_STORE, { keyPath: "id", autoIncrement: true });
        }
      },
    });
  }
  return dbPromise;
}

// Test-only: force a fresh connection after the underlying DB was deleted.
export function _resetDbHandle(): void {
  dbPromise = null;
}

export async function cacheGet(key: string): Promise<CacheEntry | undefined> {
  const db = await getDb();
  return db.get(CACHE_STORE, key);
}

export async function cacheSet(key: string, data: unknown): Promise<void> {
  const db = await getDb();
  await db.put(CACHE_STORE, { data, cachedAt: Date.now() }, key);
}

export async function cacheEntries(): Promise<Array<[string, CacheEntry]>> {
  const db = await getDb();
  const keys = await db.getAllKeys(CACHE_STORE);
  const values = await db.getAll(CACHE_STORE);
  return keys.map((k, i) => [String(k), values[i] as CacheEntry]);
}

export async function queueAdd(type: QueueType, payload: unknown): Promise<number> {
  const db = await getDb();
  const id = await db.add(QUEUE_STORE, { type, payload, createdAt: Date.now() });
  return id as number;
}

export async function queueAll(): Promise<QueueEntry[]> {
  const db = await getDb();
  return (await db.getAll(QUEUE_STORE)) as QueueEntry[];
}

export async function queueDelete(id: number): Promise<void> {
  const db = await getDb();
  await db.delete(QUEUE_STORE, id);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/offlineDb.test.ts`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
cd web && git add src/lib/offlineDb.ts src/lib/offlineDb.test.ts
git commit -m "feat: add IndexedDB cache + queue stores for offline mode"
```

---

### Task 3: `config.ts` extraction + `connectivity.ts`

**Files:**
- Create: `web/src/lib/config.ts`
- Modify: `web/src/lib/api.ts:1-18` (replace the token/base-URL block with a re-export)
- Create: `web/src/lib/connectivity.ts`
- Test: `web/src/lib/connectivity.test.ts`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `config.ts`: `getToken(): string`, `setToken(t: string): void`, `getApiBase(): string`, `setApiBase(b: string): void`
  - `connectivity.ts`: `isOnline(): boolean`, `subscribe(fn: (online: boolean) => void): () => void`, `ping(): Promise<boolean>`, `startPolling(intervalMs?: number): void`, `stopPolling(): void`, `notifyFetchFailed(): void`, `_resetForTests(): void` (test-only)

**Why this split:** `api.ts` will need to import `connectivity.ts` (to call `notifyFetchFailed`), and `connectivity.ts` needs `getApiBase()` to ping the right host. Keeping `getApiBase`/`getToken` in `api.ts` would create a circular import between the two files, so they move to a tiny shared `config.ts` that both import. `api.ts` re-exports them so `web/src/pages/Settings.tsx`'s existing `import { ... } from "../lib/api"` keeps working unchanged.

- [ ] **Step 1: Extract `config.ts`**

Create `web/src/lib/config.ts`:
```ts
// Local device config: bearer token + API base URL (single-user, localStorage-backed).

const TOKEN_KEY = "subjects_token";
const BASE_KEY = "subjects_api_base";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}
export function setToken(t: string): void {
  localStorage.setItem(TOKEN_KEY, t);
}
export function getApiBase(): string {
  // Empty => same origin (dev proxy / docker web reverse-proxy).
  return localStorage.getItem(BASE_KEY) || "";
}
export function setApiBase(b: string): void {
  localStorage.setItem(BASE_KEY, b.replace(/\/$/, ""));
}
```

- [ ] **Step 2: Point `api.ts` at it**

In `web/src/lib/api.ts`, replace lines 1-18 (the comment header through `setApiBase`):

Old:
```ts
// Thin API client. Base URL + token from localStorage (single-user).

const TOKEN_KEY = "subjects_token";
const BASE_KEY = "subjects_api_base";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function getApiBase(): string {
  // Empty => same origin (dev proxy / docker web reverse-proxy).
  return localStorage.getItem(BASE_KEY) || "";
}
export function setApiBase(b: string) {
  localStorage.setItem(BASE_KEY, b.replace(/\/$/, ""));
}
```

New:
```ts
// Thin API client. Base URL + token from localStorage (single-user).
export { getToken, setToken, getApiBase, setApiBase } from "./config";
import { getApiBase, getToken } from "./config";
```

- [ ] **Step 3: Verify the app still typechecks**

Run: `cd web && npx tsc -b`
Expected: no errors.

- [ ] **Step 4: Write the failing connectivity tests**

Create `web/src/lib/connectivity.test.ts`:
```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetForTests, isOnline, notifyFetchFailed, ping, subscribe } from "./connectivity";

beforeEach(() => {
  _resetForTests();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("connectivity", () => {
  it("starts online by default", () => {
    expect(isOnline()).toBe(true);
  });

  it("ping() flips offline on a rejected fetch", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const ok = await ping();
    expect(ok).toBe(false);
    expect(isOnline()).toBe(false);
  });

  it("ping() flips back online on a successful fetch", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    await ping();
    expect(isOnline()).toBe(false);

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true } as Response));
    const ok = await ping();
    expect(ok).toBe(true);
    expect(isOnline()).toBe(true);
  });

  it("notifies subscribers only when the state actually changes", async () => {
    const seen: boolean[] = [];
    const unsubscribe = subscribe((v) => seen.push(v));

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true } as Response));
    await ping(); // already online -> no change -> no notification

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    await ping(); // online -> offline -> notified

    unsubscribe();
    expect(seen).toEqual([false]);
  });

  it("notifyFetchFailed() triggers a ping", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("down"));
    vi.stubGlobal("fetch", fetchMock);
    notifyFetchFailed();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });
});
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/connectivity.test.ts`
Expected: FAIL — `Cannot find module './connectivity'`.

- [ ] **Step 6: Implement `connectivity.ts`**

Create `web/src/lib/connectivity.ts`:
```ts
import { getApiBase } from "./config";

export type ConnectivityListener = (online: boolean) => void;

const listeners = new Set<ConnectivityListener>();
let online = true;
let timer: ReturnType<typeof setInterval> | null = null;

function setOnline(next: boolean): void {
  if (next === online) return;
  online = next;
  listeners.forEach((fn) => fn(online));
}

export function isOnline(): boolean {
  return online;
}

export function subscribe(fn: ConnectivityListener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export async function ping(): Promise<boolean> {
  const ctrl = new AbortController();
  const timeout = setTimeout(() => ctrl.abort(), 4000);
  try {
    const resp = await fetch(`${getApiBase()}/api/health`, { cache: "no-store", signal: ctrl.signal });
    setOnline(resp.ok);
    return resp.ok;
  } catch {
    setOnline(false);
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

export function startPolling(intervalMs = 12000): void {
  if (timer) return;
  void ping();
  timer = setInterval(() => void ping(), intervalMs);
}

export function stopPolling(): void {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

export function notifyFetchFailed(): void {
  void ping();
}

// Test-only: reset module-level state between tests.
export function _resetForTests(): void {
  stopPolling();
  online = true;
  listeners.clear();
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/connectivity.test.ts`
Expected: `5 passed`.

- [ ] **Step 8: Commit**

```bash
cd web && git add src/lib/config.ts src/lib/api.ts src/lib/connectivity.ts src/lib/connectivity.test.ts
git commit -m "feat: add connectivity detection via /api/health polling"
```

---

### Task 4: `offlineQueue.ts` — enqueue, counts, replay, error taxonomy

**Files:**
- Create: `web/src/lib/offlineQueue.ts`
- Test: `web/src/lib/offlineQueue.test.ts`

**Interfaces:**
- Consumes: `queueAdd`, `queueAll`, `queueDelete`, `QueueEntry`, `QueueType` from `./offlineDb` (Task 2); `subscribe` from `./connectivity` (Task 3).
- Produces:
  - `type QueueCounts = Partial<Record<QueueType, number>>`
  - `interface IssueNote { message: string; at: number }`
  - `type Executor = (payload: unknown) => Promise<Response>`
  - `registerExecutors(map: Partial<Record<QueueType, Executor>>): void`
  - `enqueue(type: QueueType, payload: unknown): Promise<number>`
  - `listCounts(): Promise<QueueCounts>`
  - `recentIssues(): IssueNote[]`
  - `isPaused(): boolean`
  - `subscribeCounts(fn: () => void): () => void`
  - `replay(): Promise<void>`
  - `_resetForTests(): void` (test-only)

- [ ] **Step 1: Write the failing tests**

Create `web/src/lib/offlineQueue.test.ts`:
```ts
import { beforeEach, describe, expect, it } from "vitest";
import { _resetDbHandle } from "./offlineDb";
import {
  _resetForTests,
  enqueue,
  isPaused,
  listCounts,
  recentIssues,
  registerExecutors,
  replay,
} from "./offlineQueue";

function resp(status: number): Response {
  return { ok: status >= 200 && status < 300, status } as Response;
}

async function wipeDb(): Promise<void> {
  _resetDbHandle();
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.deleteDatabase("subjects-offline");
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    req.onblocked = () => resolve();
  });
}

beforeEach(async () => {
  await wipeDb();
  _resetForTests();
});

describe("offlineQueue", () => {
  it("groups pending entries by type", async () => {
    await enqueue("approve", { id: "1" });
    await enqueue("approve", { id: "2" });
    await enqueue("reject", { id: "3" });
    expect(await listCounts()).toEqual({ approve: 2, reject: 1 });
  });

  it("replay(): success dequeues the entry", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({ approve: async () => resp(200) });
    await replay();
    expect(await listCounts()).toEqual({});
  });

  it("replay(): a network error stops the round and preserves the queue", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({
      approve: async () => {
        throw new TypeError("Failed to fetch");
      },
    });
    await replay();
    expect(await listCounts()).toEqual({ approve: 1 });
  });

  it("replay(): a 401 pauses the queue and preserves it", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({ approve: async () => resp(401) });
    await replay();
    expect(await listCounts()).toEqual({ approve: 1 });
    expect(isPaused()).toBe(true);
  });

  it("replay(): a 409 conflict drops the entry and logs an issue", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({ approve: async () => resp(409) });
    await replay();
    expect(await listCounts()).toEqual({});
    expect(recentIssues()).toHaveLength(1);
    expect(recentIssues()[0].message).toContain("409");
  });

  it("replay(): a 500 stops the round without dropping the entry", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({ approve: async () => resp(500) });
    await replay();
    expect(await listCounts()).toEqual({ approve: 1 });
    expect(recentIssues()).toHaveLength(0);
  });

  it("replay(): processes multiple queued entries in order", async () => {
    const calls: string[] = [];
    await enqueue("approve", { id: "1" });
    await enqueue("reject", { id: "2" });
    registerExecutors({
      approve: async () => {
        calls.push("approve");
        return resp(200);
      },
      reject: async () => {
        calls.push("reject");
        return resp(200);
      },
    });
    await replay();
    expect(calls).toEqual(["approve", "reject"]);
    expect(await listCounts()).toEqual({});
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/offlineQueue.test.ts`
Expected: FAIL — `Cannot find module './offlineQueue'`.

- [ ] **Step 3: Implement `offlineQueue.ts`**

Create `web/src/lib/offlineQueue.ts`:
```ts
import { queueAdd, queueAll, queueDelete, type QueueEntry, type QueueType } from "./offlineDb";
import { subscribe as subscribeConnectivity } from "./connectivity";

export type QueueCounts = Partial<Record<QueueType, number>>;

export interface IssueNote {
  message: string;
  at: number;
}

export type Executor = (payload: unknown) => Promise<Response>;

const MAX_ISSUES = 20;
let issues: IssueNote[] = [];
let replaying = false;
let paused = false;
let executors: Partial<Record<QueueType, Executor>> = {};

type Listener = () => void;
const countsListeners = new Set<Listener>();

function notifyCountsChanged(): void {
  countsListeners.forEach((fn) => fn());
}

export function registerExecutors(map: Partial<Record<QueueType, Executor>>): void {
  executors = { ...executors, ...map };
}

export async function enqueue(type: QueueType, payload: unknown): Promise<number> {
  const id = await queueAdd(type, payload);
  notifyCountsChanged();
  return id;
}

export async function listCounts(): Promise<QueueCounts> {
  const all = await queueAll();
  const counts: QueueCounts = {};
  for (const entry of all) {
    counts[entry.type] = (counts[entry.type] || 0) + 1;
  }
  return counts;
}

export function recentIssues(): IssueNote[] {
  return issues.slice();
}

export function isPaused(): boolean {
  return paused;
}

export function subscribeCounts(fn: Listener): () => void {
  countsListeners.add(fn);
  return () => countsListeners.delete(fn);
}

function addIssue(message: string): void {
  issues.push({ message, at: Date.now() });
  if (issues.length > MAX_ISSUES) issues.shift();
}

export async function replay(): Promise<void> {
  if (replaying) return;
  replaying = true;
  try {
    for (;;) {
      const all: QueueEntry[] = await queueAll();
      if (all.length === 0) {
        paused = false;
        return;
      }
      const entry = all[0];
      const exec = executors[entry.type];
      if (!exec) {
        await queueDelete(entry.id);
        notifyCountsChanged();
        continue;
      }
      let response: Response;
      try {
        response = await exec(entry.payload);
      } catch {
        return; // network error: stop this round, still offline
      }
      if (response.ok) {
        paused = false;
        await queueDelete(entry.id);
        notifyCountsChanged();
        continue;
      }
      if (response.status === 401) {
        paused = true;
        return;
      }
      if (response.status >= 500) {
        return; // transient server issue: stop the round, keep the entry
      }
      addIssue(`${entry.type} — skipped (HTTP ${response.status})`);
      await queueDelete(entry.id);
      notifyCountsChanged();
    }
  } finally {
    replaying = false;
  }
}

subscribeConnectivity((online) => {
  if (online) void replay();
});

// Test-only: reset module-level state between tests.
export function _resetForTests(): void {
  issues = [];
  replaying = false;
  paused = false;
  executors = {};
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/offlineQueue.test.ts`
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
cd web && git add src/lib/offlineQueue.ts src/lib/offlineQueue.test.ts
git commit -m "feat: add offline mutation queue with replay + error taxonomy"
```

---

### Task 5: Wire `api.ts` — cache-fallback reads, optimistic queued mutations

**Files:**
- Modify: `web/src/lib/api.ts` (full rewrite of the `api` object + new helpers; imports/types/interfaces unchanged)
- Test: `web/src/lib/api.offline.test.ts`

**Interfaces:**
- Consumes: `cacheGet`, `cacheSet`, `cacheEntries` from `./offlineDb` (Task 2); `notifyFetchFailed` from `./connectivity` (Task 3); `enqueue`, `registerExecutors` from `./offlineQueue` (Task 4).
- Produces: no new public exports — `api.*`, `Item`, `Category`, `TreeNode`, `SettingsPayload`, `mediaUrl` keep their existing shapes; behavior only.

Read `web/src/lib/api.ts` in full before editing — this task replaces everything from the `function url(...)` helper (currently line 20) through the end of the `api` object (currently line 145), and appends executor registration at the bottom of the file.

- [ ] **Step 1: Write the failing tests**

Create `web/src/lib/api.offline.test.ts`:
```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetDbHandle } from "./offlineDb";
import { _resetForTests as resetQueue } from "./offlineQueue";
import { _resetForTests as resetConnectivity } from "./connectivity";
import { api } from "./api";

async function wipeDb(): Promise<void> {
  _resetDbHandle();
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.deleteDatabase("subjects-offline");
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    req.onblocked = () => resolve();
  });
}

beforeEach(async () => {
  await wipeDb();
  resetQueue();
  resetConnectivity();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api offline fallback", () => {
  it("getItem() falls back to the cache on a network error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "1", title: "Cached" }), { status: 200 }),
      )
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await api.getItem("1"); // primes the cache
    const item = await api.getItem("1"); // network fails -> cache fallback
    expect(item.title).toBe("Cached");
  });

  it("approve() enqueues and returns an optimistically patched item when offline", async () => {
    const listed = new Response(
      JSON.stringify([{ id: "1", title: "T", status: "needs_review" }]),
      { status: 200 },
    );
    const fetchMock = vi.fn().mockResolvedValueOnce(listed).mockRejectedValueOnce(new TypeError("down"));
    vi.stubGlobal("fetch", fetchMock);

    await api.listItems(); // primes the /api/items cache
    const patched = await api.approve("1");
    expect(patched.status).toBe("enriched");
  });

  it("ingestJSON() enqueues a capture and returns a synthetic id when offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    const result = await api.ingestJSON({ url: "https://example.com" });
    expect(result.id).toMatch(/^local:/);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npx vitest run src/lib/api.offline.test.ts`
Expected: FAIL (offline fallback behavior doesn't exist yet — `approve()`/`getItem()` reject instead of falling back).

- [ ] **Step 3: Rewrite `api.ts`**

Replace everything in `web/src/lib/api.ts` from the `function url(...)` helper (line 20) to the end of the file with:

```ts
import { cacheEntries, cacheGet, cacheSet } from "./offlineDb";
import { notifyFetchFailed } from "./connectivity";
import { enqueue, registerExecutors } from "./offlineQueue";

function url(path: string): string {
  return `${getApiBase()}${path}`;
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`${resp.status} ${resp.statusText}: ${text}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

// Only a network-level failure (fetch's promise rejecting, e.g. TypeError in
// browsers) should trigger offline fallback/queuing — a resolved-but-non-ok
// response still throws via handle() so the online error path is unchanged.
function isNetworkError(e: unknown): e is TypeError {
  if (e instanceof TypeError) {
    notifyFetchFailed();
    return true;
  }
  return false;
}

async function cachedGet<T>(path: string, doFetch: () => Promise<Response>): Promise<T> {
  const key = url(path);
  try {
    const data = await handle<T>(await doFetch());
    await cacheSet(key, data);
    return data;
  } catch (e) {
    if (isNetworkError(e)) {
      const cached = await cacheGet(key);
      if (cached) return cached.data as T;
    }
    throw e;
  }
}

async function patchCachedItems(id: string, mutate: (item: Item) => Item | null): Promise<void> {
  for (const [key, entry] of await cacheEntries()) {
    if (!key.includes("/api/items")) continue;
    const data = entry.data;
    if (Array.isArray(data)) {
      const items = data as Item[];
      const idx = items.findIndex((it) => it.id === id);
      if (idx === -1) continue;
      const result = mutate(items[idx]);
      const next = items.slice();
      if (result === null) next.splice(idx, 1);
      else next[idx] = result;
      await cacheSet(key, next);
    } else if (data && typeof data === "object" && (data as Item).id === id) {
      const result = mutate(data as Item);
      if (result !== null) await cacheSet(key, result);
    }
  }
}

async function insertPlaceholderItem(item: Item): Promise<void> {
  const listKey = url("/api/items");
  const listEntry = await cacheGet(listKey);
  const list = Array.isArray(listEntry?.data) ? (listEntry!.data as Item[]) : [];
  await cacheSet(listKey, [item, ...list]);
  await cacheSet(url(`/api/items/${item.id}`), item);
}

function placeholderItem(fields: { url?: string; text?: string; title?: string }, queueId: number): Item {
  const now = new Date().toISOString();
  return {
    id: `local:${queueId}`,
    type: "unknown",
    status: "pending",
    title: fields.title || fields.url || (fields.text ? fields.text.slice(0, 60) : "Queued capture"),
    description: fields.text && fields.text !== fields.title ? fields.text : null,
    canonical_url: fields.url || null,
    icon_url: null,
    thumbnail_url: null,
    attributes: {},
    links: {},
    source: {},
    resolver_id: null,
    confidence: null,
    created_at: now,
    updated_at: now,
    tags: [],
    categories: [],
  };
}

async function patchCachedSettings(patch: Record<string, string>): Promise<void> {
  const key = url("/api/settings");
  const entry = await cacheGet(key);
  if (!entry) return;
  const data = entry.data as SettingsPayload;
  await cacheSet(key, {
    ...data,
    overrides: { ...data.overrides, ...patch },
    effective: { ...data.effective, ...patch },
  });
}

async function patchCachedCategories(mutate: (cats: Category[]) => Category[]): Promise<void> {
  const key = url("/api/categories");
  const entry = await cacheGet(key);
  const list = Array.isArray(entry?.data) ? (entry!.data as Category[]) : [];
  await cacheSet(key, mutate(list));
}

export interface Tag {
  id: string;
  name: string;
}
export interface Category {
  id: string;
  name: string;
  parent_id: string | null;
}
export interface Item {
  id: string;
  type: string;
  status: string;
  title: string | null;
  description: string | null;
  canonical_url: string | null;
  icon_url: string | null;
  thumbnail_url: string | null;
  attributes: Record<string, unknown>;
  links: Record<string, string>;
  source: Record<string, unknown>;
  resolver_id: string | null;
  confidence: number | null;
  created_at: string;
  updated_at: string;
  tags: Tag[];
  categories: Category[];
}
export interface TreeNode {
  id: string;
  name: string;
  parent_id: string | null;
  count: number;
  children: TreeNode[];
}

type CaptureExecutorPayload =
  | { kind: "json"; body: { url?: string; text?: string; title?: string } }
  | { kind: "form"; fields: { title?: string; text?: string; url?: string }; media: File | null };

export const api = {
  async listItems(params: Record<string, string> = {}): Promise<Item[]> {
    const q = new URLSearchParams(params).toString();
    const path = `/api/items${q ? "?" + q : ""}`;
    return cachedGet<Item[]>(path, () => fetch(url(path)));
  },
  async getItem(id: string): Promise<Item> {
    const path = `/api/items/${id}`;
    return cachedGet<Item>(path, () => fetch(url(path)));
  },
  async ingestJSON(body: { url?: string; text?: string; title?: string }): Promise<{ id: string }> {
    const path = `/api/ingest`;
    try {
      return await handle(
        await fetch(url(path), {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Subjects-Channel": "web", ...authHeaders() },
          body: JSON.stringify(body),
        }),
      );
    } catch (e) {
      if (!isNetworkError(e)) throw e;
      const queueId = await enqueue("capture", { kind: "json", body } satisfies CaptureExecutorPayload);
      const item = placeholderItem(body, queueId);
      await insertPlaceholderItem(item);
      return { id: item.id };
    }
  },
  async ingestForm(form: FormData): Promise<{ id: string }> {
    const path = `/api/ingest`;
    try {
      return await handle(
        await fetch(url(path), {
          method: "POST",
          headers: { "X-Subjects-Channel": "web", ...authHeaders() },
          body: form,
        }),
      );
    } catch (e) {
      if (!isNetworkError(e)) throw e;
      const fields = {
        title: form.get("title")?.toString(),
        text: form.get("text")?.toString(),
        url: form.get("url")?.toString(),
      };
      const media = form.get("media");
      const payload: CaptureExecutorPayload = {
        kind: "form",
        fields,
        media: media instanceof File ? media : null,
      };
      const queueId = await enqueue("capture", payload);
      const item = placeholderItem(fields, queueId);
      await insertPlaceholderItem(item);
      return { id: item.id };
    }
  },
  async approve(id: string): Promise<Item> {
    const path = `/api/items/${id}/approve`;
    try {
      return await handle(await fetch(url(path), { method: "POST", headers: authHeaders() }));
    } catch (e) {
      if (!isNetworkError(e)) throw e;
      await enqueue("approve", { id });
      let patched: Item | null = null;
      await patchCachedItems(id, (item) => {
        patched = { ...item, status: "enriched" };
        return patched;
      });
      if (!patched) throw e;
      return patched;
    }
  },
  async reject(id: string): Promise<Item> {
    const path = `/api/items/${id}/reject`;
    try {
      return await handle(await fetch(url(path), { method: "POST", headers: authHeaders() }));
    } catch (e) {
      if (!isNetworkError(e)) throw e;
      await enqueue("reject", { id });
      let patched: Item | null = null;
      await patchCachedItems(id, (item) => {
        patched = { ...item, status: "rejected" };
        return patched;
      });
      if (!patched) throw e;
      return patched;
    }
  },
  async reprocess(id: string): Promise<void> {
    const path = `/api/items/${id}/reprocess`;
    try {
      await handle(await fetch(url(path), { method: "POST", headers: authHeaders() }));
    } catch (e) {
      if (!isNetworkError(e)) throw e;
      await enqueue("reprocess", { id });
    }
  },
  async remove(id: string): Promise<void> {
    const path = `/api/items/${id}`;
    try {
      await handle(await fetch(url(path), { method: "DELETE", headers: authHeaders() }));
    } catch (e) {
      if (!isNetworkError(e)) throw e;
      await enqueue("remove", { id });
      await patchCachedItems(id, () => null);
    }
  },
  async categories(): Promise<Category[]> {
    const path = `/api/categories`;
    return cachedGet<Category[]>(path, () => fetch(url(path)));
  },
  async tree(): Promise<TreeNode[]> {
    const path = `/api/categories/tree`;
    return cachedGet<TreeNode[]>(path, () => fetch(url(path)));
  },
  async createCategory(name: string, parent_id: string | null): Promise<Category> {
    const path = `/api/categories`;
    try {
      return await handle(
        await fetch(url(path), {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ name, parent_id }),
        }),
      );
    } catch (e) {
      if (!isNetworkError(e)) throw e;
      await enqueue("category_create", { name, parent_id });
      const category: Category = { id: `local:${Date.now()}`, name, parent_id };
      await patchCachedCategories((cats) => [...cats, category]);
      return category;
    }
  },
  async deleteCategory(id: string): Promise<void> {
    const path = `/api/categories/${id}`;
    try {
      await handle(await fetch(url(path), { method: "DELETE", headers: authHeaders() }));
    } catch (e) {
      if (!isNetworkError(e)) throw e;
      await enqueue("category_delete", { id });
      await patchCachedCategories((cats) => cats.filter((c) => c.id !== id));
    }
  },
  async search(q: string, mode: "fulltext" | "semantic"): Promise<{ hits: Partial<Item>[] }> {
    const path = `/api/search?q=${encodeURIComponent(q)}&mode=${mode}`;
    return cachedGet(path, () => fetch(url(path)));
  },
  async getSettings(): Promise<SettingsPayload> {
    const path = `/api/settings`;
    return cachedGet<SettingsPayload>(path, () => fetch(url(path), { headers: authHeaders() }));
  },
  async updateSettings(patch: Record<string, string>): Promise<void> {
    const path = `/api/settings`;
    try {
      await handle(
        await fetch(url(path), {
          method: "PUT",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify(patch),
        }),
      );
    } catch (e) {
      if (!isNetworkError(e)) throw e;
      await enqueue("settings_update", patch);
      await patchCachedSettings(patch);
    }
  },
};

export interface SettingsPayload {
  ai_provider: string;
  effective: Record<string, string>;
  overrides: Record<string, string>;
  defaults: Record<string, string>;
  keys_present: Record<string, boolean>;
  editable_keys: string[];
}

export function mediaUrl(item: Item): string | null {
  if (item.thumbnail_url) return item.thumbnail_url;
  const mp = item.source?.media_path as string | undefined;
  if (mp) {
    const name = mp.split(/[/\\]/).pop();
    return url(`/api/media/${name}`);
  }
  return null;
}

// Raw executors used by offlineQueue.replay() — return the bare Response so
// the queue can inspect status codes without handle()'s throw-on-!ok.
registerExecutors({
  capture: async (payload) => {
    const p = payload as CaptureExecutorPayload;
    if (p.kind === "json") {
      return fetch(url("/api/ingest"), {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Subjects-Channel": "web", ...authHeaders() },
        body: JSON.stringify(p.body),
      });
    }
    const form = new FormData();
    if (p.fields.title) form.append("title", p.fields.title);
    if (p.fields.text) form.append("text", p.fields.text);
    if (p.fields.url) form.append("url", p.fields.url);
    if (p.media) form.append("media", p.media, p.media.name);
    return fetch(url("/api/ingest"), {
      method: "POST",
      headers: { "X-Subjects-Channel": "web", ...authHeaders() },
      body: form,
    });
  },
  approve: (payload) =>
    fetch(url(`/api/items/${(payload as { id: string }).id}/approve`), { method: "POST", headers: authHeaders() }),
  reject: (payload) =>
    fetch(url(`/api/items/${(payload as { id: string }).id}/reject`), { method: "POST", headers: authHeaders() }),
  reprocess: (payload) =>
    fetch(url(`/api/items/${(payload as { id: string }).id}/reprocess`), { method: "POST", headers: authHeaders() }),
  remove: (payload) =>
    fetch(url(`/api/items/${(payload as { id: string }).id}`), { method: "DELETE", headers: authHeaders() }),
  category_create: (payload) =>
    fetch(url("/api/categories"), {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(payload),
    }),
  category_delete: (payload) =>
    fetch(url(`/api/categories/${(payload as { id: string }).id}`), { method: "DELETE", headers: authHeaders() }),
  settings_update: (payload) =>
    fetch(url("/api/settings"), {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(payload),
    }),
});
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npx vitest run src/lib/api.offline.test.ts`
Expected: `3 passed`.

- [ ] **Step 5: Run the full test suite + typecheck**

Run: `cd web && npm test && npx tsc -b`
Expected: all tests pass, no type errors.

- [ ] **Step 6: Commit**

```bash
cd web && git add src/lib/api.ts src/lib/api.offline.test.ts
git commit -m "feat: cache GET fallback + queue-on-offline for every api.ts mutation"
```

---

### Task 6: `SyncStatusPill` — nav-bar online/offline + pending-by-type panel

**Files:**
- Create: `web/src/lib/offlineHooks.ts`
- Create: `web/src/components/SyncStatusPill.tsx`
- Modify: `web/src/App.tsx`

**Interfaces:**
- Consumes: `isOnline`, `subscribe`, `startPolling` from `./connectivity`; `listCounts`, `recentIssues`, `isPaused`, `subscribeCounts`, `replay`, `type QueueCounts` from `./offlineQueue` (Task 4).
- Produces: `useOnlineStatus(): boolean`, `useQueueCounts(): { counts: QueueCounts; total: number; issues: string[]; paused: boolean }`, default-exported `SyncStatusPill` component.

This task is UI — verify manually (Chrome DevTools "Offline" throttle) rather than with Vitest, per the spec's testing section.

- [ ] **Step 1: Write the hooks**

Create `web/src/lib/offlineHooks.ts`:
```ts
import { useEffect, useState } from "react";
import { isOnline, subscribe } from "./connectivity";
import { isPaused, listCounts, recentIssues, subscribeCounts, type QueueCounts } from "./offlineQueue";

export function useOnlineStatus(): boolean {
  const [online, setOnlineState] = useState(isOnline());
  useEffect(() => subscribe(setOnlineState), []);
  return online;
}

export interface QueueStatus {
  counts: QueueCounts;
  total: number;
  issues: string[];
  paused: boolean;
}

export function useQueueCounts(): QueueStatus {
  const [counts, setCounts] = useState<QueueCounts>({});
  const [issues, setIssues] = useState<string[]>([]);
  const [paused, setPaused] = useState(isPaused());

  useEffect(() => {
    async function refresh() {
      setCounts(await listCounts());
      setIssues(recentIssues().map((i) => i.message));
      setPaused(isPaused());
    }
    refresh();
    return subscribeCounts(refresh);
  }, []);

  const total = Object.values(counts).reduce((sum, n) => sum + (n || 0), 0);
  return { counts, total, issues, paused };
}
```

- [ ] **Step 2: Write the component**

Create `web/src/components/SyncStatusPill.tsx`:
```tsx
import { useState } from "react";
import { useOnlineStatus, useQueueCounts } from "../lib/offlineHooks";
import { replay } from "../lib/offlineQueue";

const TYPE_LABELS: Record<string, string> = {
  capture: "capture",
  approve: "approve",
  reject: "reject",
  reprocess: "reprocess",
  remove: "delete",
  category_create: "category add",
  category_delete: "category delete",
  settings_update: "settings",
};

export default function SyncStatusPill() {
  const online = useOnlineStatus();
  const { counts, total, issues, paused } = useQueueCounts();
  const [open, setOpen] = useState(false);

  const label = paused ? "Sync paused" : online ? (total > 0 ? "Syncing" : "Online") : "Offline";
  const color = paused
    ? "bg-amber-900/40 text-amber-300"
    : online
      ? total > 0
        ? "bg-sky-900/40 text-sky-300"
        : "bg-emerald-900/40 text-emerald-300"
      : "bg-rose-900/40 text-rose-300";

  return (
    <div className="relative ml-auto">
      <button onClick={() => setOpen((v) => !v)} className={`rounded px-2 py-1 text-xs font-medium ${color}`}>
        {label}
        {total > 0 && <span className="ml-1">({total})</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-64 rounded-lg border border-slate-800 bg-slate-900 p-3 text-xs shadow-xl">
          {paused && <p className="mb-2 text-amber-300">Sync paused — check your token in Settings.</p>}
          {total === 0 && !paused && <p className="text-slate-500">Nothing pending.</p>}
          {Object.entries(counts).map(([type, count]) => (
            <div key={type} className="flex justify-between py-0.5 text-slate-300">
              <span>{TYPE_LABELS[type] || type}</span>
              <span>{count}</span>
            </div>
          ))}
          <button
            onClick={() => void replay()}
            className="mt-2 w-full rounded bg-slate-800 py-1 text-slate-200 hover:bg-slate-700"
          >
            Retry now
          </button>
          {issues.length > 0 && (
            <div className="mt-2 border-t border-slate-800 pt-2 text-slate-500">
              {issues.slice(-5).map((msg, i) => (
                <p key={i} className="truncate">
                  {msg}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Wire it into the nav**

In `web/src/App.tsx`, add the import and start polling on mount, and render the pill after the tabs.

Change:
```tsx
import { NavLink, Route, Routes } from "react-router-dom";
import Inbox from "./pages/Inbox";
```
to:
```tsx
import { useEffect } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { startPolling } from "./lib/connectivity";
import SyncStatusPill from "./components/SyncStatusPill";
import Inbox from "./pages/Inbox";
```

Change:
```tsx
export default function App() {
  return (
```
to:
```tsx
export default function App() {
  useEffect(() => {
    startPolling();
  }, []);

  return (
```

Change:
```tsx
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `rounded px-3 py-1.5 transition ${
                  isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
```
to:
```tsx
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `rounded px-3 py-1.5 transition ${
                  isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
          <SyncStatusPill />
        </nav>
```

- [ ] **Step 4: Typecheck + build**

Run: `cd web && npx tsc -b && npm run build`
Expected: no errors, build succeeds.

- [ ] **Step 5: Manual verification**

Run: `cd web && npm run dev`, open the app, open Chrome DevTools → Network → set throttling to "Offline". Confirm the nav pill flips to "Offline" within ~15s (health poll) or immediately after attempting an action. Capture a URL while offline; confirm a "pending" placeholder card appears in the Inbox and the pill shows `capture (1)`. Approve/reject an existing item while offline; confirm its status changes immediately and the pill count increments. Switch DevTools back to "Online"; confirm the pill drains back to "Online" and the placeholder resolves into (or is replaced by) the real synced item.

- [ ] **Step 6: Commit**

```bash
cd web && git add src/lib/offlineHooks.ts src/components/SyncStatusPill.tsx src/App.tsx
git commit -m "feat: add nav-bar sync status pill with pending-by-type panel"
```

---

### Task 7: Inbox live-refresh on queue changes + docs

**Files:**
- Modify: `web/src/pages/Inbox.tsx`
- Modify: `docs/USER_MANUAL.md`

**Interfaces:**
- Consumes: `subscribeCounts` from `../lib/offlineQueue` (Task 4).

Task 5 already makes `api.listItems()` return cached data (including any locally-inserted placeholder) when offline. `Inbox.tsx` currently only re-runs `refresh()` on mount and on SSE events — neither fires when a capture is queued offline (no server-sent event exists yet) or when a queued capture finishes replaying. Subscribing `refresh()` to the queue's change notifications closes that gap with a one-line addition; no placeholder-merging logic needed in the component itself.

- [ ] **Step 1: Wire the refresh**

In `web/src/pages/Inbox.tsx`, change:
```tsx
import { useEffect, useRef, useState } from "react";
import { api, Item } from "../lib/api";
import { subscribeEvents } from "../lib/sse";
import ItemCard from "../components/ItemCard";
```
to:
```tsx
import { useEffect, useRef, useState } from "react";
import { api, Item } from "../lib/api";
import { subscribeEvents } from "../lib/sse";
import { subscribeCounts } from "../lib/offlineQueue";
import ItemCard from "../components/ItemCard";
```

And change:
```tsx
  useEffect(() => {
    refresh();
    // Live updates: re-fetch the changed item and splice it in (or prepend if new).
    return subscribeEvents(async (ev) => {
      try {
        const it = await api.getItem(ev.item_id);
        setItems((prev) => {
          const i = prev.findIndex((p) => p.id === it.id);
          if (i === -1) return [it, ...prev];
          const next = prev.slice();
          next[i] = it;
          return next;
        });
      } catch {
        refresh();
      }
    });
  }, []);
```
to:
```tsx
  useEffect(() => {
    refresh();
    // Live updates: re-fetch the changed item and splice it in (or prepend if new).
    const unsubscribeEvents = subscribeEvents(async (ev) => {
      try {
        const it = await api.getItem(ev.item_id);
        setItems((prev) => {
          const i = prev.findIndex((p) => p.id === it.id);
          if (i === -1) return [it, ...prev];
          const next = prev.slice();
          next[i] = it;
          return next;
        });
      } catch {
        refresh();
      }
    });
    // Re-list on every queue change: picks up newly-queued offline placeholders
    // immediately, and replaces them with the real synced item once replayed.
    const unsubscribeQueue = subscribeCounts(refresh);
    return () => {
      unsubscribeEvents();
      unsubscribeQueue();
    };
  }, []);
```

- [ ] **Step 2: Typecheck + build**

Run: `cd web && npx tsc -b && npm run build`
Expected: no errors.

- [ ] **Step 3: Manual verification**

Run: `cd web && npm run dev`, go offline in DevTools, capture a URL — confirm the placeholder appears in Inbox without a page reload. Go back online and wait for the pill to drain — confirm the placeholder is replaced by the real item without a page reload.

- [ ] **Step 4: Update the user manual**

In `docs/USER_MANUAL.md`, find the `### Inbox — capture + live feed` section and add a paragraph after it describing offline mode. Read the section first to match its existing tone, then insert (after that section's existing content, before the next `###` heading):

```markdown
**Offline mode.** If the app can't reach the server (nav pill shows "Offline"),
captures, approvals/rejections, category edits, and settings changes all still
work — they're queued in the browser and replayed automatically once the
connection comes back. Click the nav pill to see what's pending, broken down
by type, and to trigger a manual retry. Anything the server rejects as stale
on replay (e.g. approving an item already deleted elsewhere) is dropped
silently with a one-line note in that same panel — everything else stays
queued until it succeeds.
```

- [ ] **Step 5: Commit**

```bash
cd web && git add src/pages/Inbox.tsx ../docs/USER_MANUAL.md
git commit -m "feat: refresh Inbox on queue changes; document offline mode"
```
