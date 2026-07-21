// Presentation helpers for the item detail panel: humanize keys, format known
// values, and turn the raw attributes bag into render-ready rows — so the panel
// never shows raw JSON.

const KEY_LABELS: Record<string, string> = {
  tmdb_id: "TMDB ID",
  imdb: "IMDb",
  apple_original: "Apple Original",
};

// Numeric keys that read better abbreviated (1200 -> 1.2k).
const COMPACT_KEYS = new Set(["votes", "stars", "forks"]);

export function compactNum(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (abs >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "k";
  return String(n);
}

export function humanizeKey(key: string): string {
  if (KEY_LABELS[key]) return KEY_LABELS[key];
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatScalar(key: string, v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") {
    if (key === "rating") return `${v.toFixed(1)} ★`;
    if (key === "runtime") return `${v} min`;
    if (COMPACT_KEYS.has(key)) return compactNum(v);
  }
  return String(v);
}

export interface AttrRow {
  key: string;
  label: string;
  kind: "chips" | "text";
  chips?: string[];
  text?: string;
}

// Only these attributes render as key-facts rows, in this order, with these labels.
const KEY_FACTS: { key: string; label: string }[] = [
  { key: "cast", label: "Cast" },
  { key: "provider", label: "Where to watch" },
  { key: "network", label: "Network" },
  { key: "genres", label: "Genres" },
];

// Curated projection of the attributes bag: only allow-listed key-facts render,
// so the panel never dumps arbitrary/internal attributes or raw JSON.
export function attrRows(attributes: Record<string, unknown>): AttrRow[] {
  const rows: AttrRow[] = [];
  for (const { key, label } of KEY_FACTS) {
    const v = attributes?.[key];
    if (Array.isArray(v)) {
      const chips = v.filter((x) => x != null && x !== "").map(String);
      if (chips.length) rows.push({ key, label, kind: "chips", chips });
    } else if (v != null && v !== "") {
      rows.push({ key, label, kind: "text", text: formatScalar(key, v) });
    }
  }
  return rows;
}

const TYPE_LABEL: Record<string, string> = { show: "Show", movie: "Movie" };

// One muted line under the title: year · runtime · rating · type. Skips unknowns.
export function metaLine(item: { type: string; attributes: Record<string, unknown> }): string {
  const a = item.attributes || {};
  const parts: string[] = [];
  if (a.year) parts.push(String(a.year));
  if (typeof a.runtime === "number") parts.push(`${a.runtime} min`);
  if (typeof a.rating === "number") parts.push(`${a.rating.toFixed(1)} ★`);
  const t = TYPE_LABEL[item.type] || humanizeKey(item.type);
  if (t) parts.push(t);
  return parts.join(" · ");
}

// Label for a canonical URL, derived from its host.
export function linkLabel(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (host.includes("themoviedb")) return "View on TMDB";
    if (host.includes("imdb")) return "View on IMDb";
    if (host.includes("github")) return "View on GitHub";
    if (host.includes("youtube") || host.includes("youtu.be")) return "Watch trailer";
    return `View on ${host}`;
  } catch {
    return "Open link";
  }
}

const LINK_KEY_LABELS: Record<string, string> = {
  trailer: "Watch trailer",
  imdb: "View on IMDb",
  homepage: "Homepage",
  repo: "Repository",
};

// Label for a key in the item's `links` dict.
export function linkKeyLabel(key: string): string {
  return LINK_KEY_LABELS[key] || humanizeKey(key);
}
