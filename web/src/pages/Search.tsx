import { useState } from "react";
import { Link } from "react-router-dom";
import { api, Item } from "../lib/api";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"fulltext" | "semantic">("fulltext");
  const [hits, setHits] = useState<Partial<Item>[]>([]);
  const [busy, setBusy] = useState(false);
  const [ran, setRan] = useState(false);

  async function run() {
    if (!q.trim()) return;
    setBusy(true);
    try {
      const r = await api.search(q.trim(), mode);
      setHits(r.hits);
      setRan(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-4 flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder="Search everything you captured…"
          className="flex-1 rounded bg-slate-900 px-3 py-2 text-sm outline-none placeholder:text-slate-600"
        />
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as "fulltext" | "semantic")}
          className="rounded bg-slate-900 px-2 text-sm"
        >
          <option value="fulltext">Full-text</option>
          <option value="semantic">Semantic</option>
        </select>
        <button onClick={run} disabled={busy} className="rounded bg-indigo-600 px-3 text-sm font-medium disabled:opacity-40">
          {busy ? "…" : "Go"}
        </button>
      </div>

      <div className="space-y-2">
        {ran && hits.length === 0 && <p className="py-8 text-center text-sm text-slate-500">No matches.</p>}
        {hits.map((h) => (
          <Link
            key={h.id}
            to={`/item/${h.id}`}
            className="block rounded-lg border border-slate-800 bg-slate-900/50 p-3 hover:border-slate-600"
          >
            <div className="flex items-center gap-2">
              <span className="truncate font-medium">{h.title || "Untitled"}</span>
              {h.type && <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400">{h.type}</span>}
            </div>
            {h.description && <p className="mt-0.5 line-clamp-2 text-sm text-slate-400">{h.description}</p>}
          </Link>
        ))}
      </div>
    </div>
  );
}
