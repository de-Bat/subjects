// Presentation helpers for the item detail panel: humanize keys, format known
// values, and turn the raw attributes bag into render-ready rows — so the panel
// never shows raw JSON.

const KEY_LABELS: Record<string, string> = {
  tmdb_id: "TMDB ID",
  imdb: "IMDb",
  apple_original: "Apple Original",
};

// Keys not worth showing in the attribute grid (internal ids / duplicated elsewhere).
const HIDDEN_KEYS = new Set(["tmdb_id", "type"]);

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

// Turn the attributes bag into rows the panel can render without any JSON.
// Drops engine metadata (`_`-prefixed), hidden/internal keys, empty values,
// and `false` boolean flags.
export function attrRows(attributes: Record<string, unknown>): AttrRow[] {
  const rows: AttrRow[] = [];
  for (const [key, v] of Object.entries(attributes || {})) {
    if (key.startsWith("_") || HIDDEN_KEYS.has(key)) continue;
    if (v === null || v === undefined || v === "") continue;

    if (Array.isArray(v)) {
      const chips = v.filter((x) => x != null && x !== "").map(String);
      if (chips.length === 0) continue;
      rows.push({ key, label: humanizeKey(key), kind: "chips", chips });
    } else if (typeof v === "boolean") {
      if (!v) continue; // hide false flags entirely
      rows.push({ key, label: humanizeKey(key), kind: "text", text: "Yes" });
    } else if (typeof v === "object") {
      // Nested object: flatten to "k: v, k: v" rather than dumping braces.
      const text = Object.entries(v as Record<string, unknown>)
        .map(([kk, vv]) => `${kk}: ${vv}`)
        .join(", ");
      if (!text) continue;
      rows.push({ key, label: humanizeKey(key), kind: "text", text });
    } else {
      rows.push({ key, label: humanizeKey(key), kind: "text", text: formatScalar(key, v) });
    }
  }
  return rows;
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
