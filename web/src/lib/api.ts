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

export const api = {
  async listItems(params: Record<string, string> = {}): Promise<Item[]> {
    const q = new URLSearchParams(params).toString();
    return handle(await fetch(url(`/api/items${q ? "?" + q : ""}`)));
  },
  async getItem(id: string): Promise<Item> {
    return handle(await fetch(url(`/api/items/${id}`)));
  },
  async ingestJSON(body: { url?: string; text?: string; title?: string }): Promise<{ id: string }> {
    return handle(
      await fetch(url(`/api/ingest`), {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Subjects-Channel": "web", ...authHeaders() },
        body: JSON.stringify(body),
      }),
    );
  },
  async ingestForm(form: FormData): Promise<{ id: string }> {
    return handle(
      await fetch(url(`/api/ingest`), {
        method: "POST",
        headers: { "X-Subjects-Channel": "web", ...authHeaders() },
        body: form,
      }),
    );
  },
  async approve(id: string): Promise<Item> {
    return handle(await fetch(url(`/api/items/${id}/approve`), { method: "POST", headers: authHeaders() }));
  },
  async reject(id: string): Promise<Item> {
    return handle(await fetch(url(`/api/items/${id}/reject`), { method: "POST", headers: authHeaders() }));
  },
  async reprocess(id: string): Promise<void> {
    return handle(await fetch(url(`/api/items/${id}/reprocess`), { method: "POST", headers: authHeaders() }));
  },
  async remove(id: string): Promise<void> {
    return handle(await fetch(url(`/api/items/${id}`), { method: "DELETE", headers: authHeaders() }));
  },
  async categories(): Promise<Category[]> {
    return handle(await fetch(url(`/api/categories`)));
  },
  async tree(): Promise<TreeNode[]> {
    return handle(await fetch(url(`/api/categories/tree`)));
  },
  async createCategory(name: string, parent_id: string | null): Promise<Category> {
    return handle(
      await fetch(url(`/api/categories`), {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ name, parent_id }),
      }),
    );
  },
  async deleteCategory(id: string): Promise<void> {
    return handle(await fetch(url(`/api/categories/${id}`), { method: "DELETE", headers: authHeaders() }));
  },
  async search(q: string, mode: "fulltext" | "semantic"): Promise<{ hits: Partial<Item>[] }> {
    return handle(await fetch(url(`/api/search?q=${encodeURIComponent(q)}&mode=${mode}`)));
  },
  async getSettings(): Promise<SettingsPayload> {
    return handle(await fetch(url(`/api/settings`), { headers: authHeaders() }));
  },
  async updateSettings(patch: Record<string, string>): Promise<void> {
    return handle(
      await fetch(url(`/api/settings`), {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(patch),
      }),
    );
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
