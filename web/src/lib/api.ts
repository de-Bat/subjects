// Thin API client. Base URL + token from localStorage (single-user).
export { getToken, setToken, getApiBase, setApiBase } from "./config";
import { getApiBase, getToken } from "./config";
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

async function cachedGet<T>(
  path: string,
  doFetch: () => Promise<Response>,
  onFetched?: (data: T) => Promise<void>,
): Promise<T> {
  const key = url(path);
  try {
    const data = await handle<T>(await doFetch());
    await cacheSet(key, data);
    if (onFetched) await onFetched(data);
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
    return cachedGet<Item[]>(path, () => fetch(url(path)), async (items) => {
      for (const item of items) {
        await cacheSet(url(`/api/items/${item.id}`), item);
      }
    });
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
      const queueId = await enqueue("category_create", { name, parent_id });
      const category: Category = { id: `local:${queueId}`, name, parent_id };
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
