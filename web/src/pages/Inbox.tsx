import { useEffect, useRef, useState } from "react";
import { api, Item } from "../lib/api";
import { subscribeEvents } from "../lib/sse";
import ItemCard from "../components/ItemCard";

// Inbox: the capture surface. Paste a URL/text, drag-drop or paste an image, and
// watch items update live via SSE as the pipeline enriches them.
export default function Inbox() {
  const [items, setItems] = useState<Item[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);

  async function refresh() {
    try {
      setItems(await api.listItems());
    } catch (e) {
      setErr(String(e));
    }
  }

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

  async function submitText() {
    const v = text.trim();
    if (!v) return;
    setBusy(true);
    setErr(null);
    try {
      const isUrl = /^https?:\/\//i.test(v);
      await api.ingestJSON(isUrl ? { url: v } : { text: v });
      setText("");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function ingestFile(file: File) {
    setBusy(true);
    setErr(null);
    try {
      const fd = new FormData();
      fd.append("media", file);
      await api.ingestForm(fd);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  function onPaste(e: React.ClipboardEvent) {
    const img = Array.from(e.clipboardData.items).find((i) => i.type.startsWith("image/"));
    if (img) {
      const f = img.getAsFile();
      if (f) {
        e.preventDefault();
        ingestFile(f);
      }
    }
  }

  const dropRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={dropRef}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files[0];
        if (f) ingestFile(f);
      }}
      className={`rounded-lg ${drag ? "outline outline-2 outline-indigo-500" : ""}`}
    >
      <div className="mb-4 rounded-lg border border-slate-800 bg-slate-900/50 p-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onPaste={onPaste}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submitText();
          }}
          placeholder="Paste a URL or text… drag/paste an image… (Ctrl/⌘+Enter)"
          rows={2}
          className="w-full resize-none rounded bg-slate-950 p-2 text-sm outline-none placeholder:text-slate-600"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-slate-500">{drag ? "Drop image to capture" : ""}</span>
          <button
            onClick={submitText}
            disabled={busy || !text.trim()}
            className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium disabled:opacity-40"
          >
            {busy ? "Capturing…" : "Capture"}
          </button>
        </div>
      </div>

      {err && <p className="mb-3 rounded bg-rose-900/40 p-2 text-sm text-rose-300">{err}</p>}

      <div className="space-y-2">
        {items.length === 0 && <p className="py-12 text-center text-sm text-slate-500">Inbox empty. Capture something.</p>}
        {items.map((it) => (
          <ItemCard key={it.id} item={it} />
        ))}
      </div>
    </div>
  );
}
