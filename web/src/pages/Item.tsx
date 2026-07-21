import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, Item, mediaUrl } from "../lib/api";
import { subscribeEvents } from "../lib/sse";
import StatusBadge from "../components/StatusBadge";
import ProcessingProgress from "../components/ProcessingProgress";

export default function ItemPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [item, setItem] = useState<Item | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [stage, setStage] = useState<string | undefined>(undefined);

  async function load() {
    if (!id) return;
    try {
      setItem(await api.getItem(id));
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    load();
    return subscribeEvents((ev) => {
      if (ev.item_id === id) {
        if (ev.stage) setStage(ev.stage);
        load();
      }
    });
  }, [id]);

  if (err) return <p className="rounded bg-rose-900/40 p-3 text-sm text-rose-300">{err}</p>;
  if (!item) return <p className="text-slate-500">Loading…</p>;

  const thumb = mediaUrl(item);
  const attrs = Object.entries(item.attributes || {});
  const links = Object.entries(item.links || {});

  async function act(fn: () => Promise<unknown>, back = false) {
    await fn();
    if (back) nav("/");
    else load();
  }

  return (
    <div>
      <ProcessingProgress status={item.status} stage={stage} />
      <div className="mb-3 flex items-center gap-2">
        <Link to="/" className="text-sm text-slate-400 hover:text-white">
          ← Inbox
        </Link>
        <StatusBadge status={item.status} />
        <span className="text-xs text-slate-500">{item.type}</span>
        {item.confidence != null && (
          <span className="text-xs text-slate-500">· {(item.confidence * 100).toFixed(0)}% conf</span>
        )}
      </div>

      {thumb && (
        <img src={thumb} alt="" className="mb-4 max-h-96 w-full rounded-lg border border-slate-800 object-contain" />
      )}

      <div className="flex items-start gap-3">
        {item.icon_url && <img src={item.icon_url} alt="" className="mt-1 h-8 w-8 rounded" />}
        <div className="min-w-0">
          <h1 className="text-xl font-semibold">{item.title || "Untitled"}</h1>
          {item.canonical_url && (
            <a
              href={item.canonical_url}
              target="_blank"
              rel="noreferrer"
              className="break-all text-sm text-indigo-400 hover:underline"
            >
              {item.canonical_url}
            </a>
          )}
        </div>
      </div>

      {item.description && <p className="mt-3 whitespace-pre-wrap text-slate-300">{item.description}</p>}

      {(item.tags.length > 0 || item.categories.length > 0) && (
        <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
          {item.categories.map((c) => (
            <Link
              key={c.id}
              to={`/categories/${encodeURIComponent(c.name)}`}
              className="rounded bg-indigo-900/40 px-1.5 py-0.5 text-indigo-300"
            >
              {c.name}
            </Link>
          ))}
          {item.tags.map((t) => (
            <span key={t.id} className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-400">
              #{t.name}
            </span>
          ))}
        </div>
      )}

      {attrs.length > 0 && (
        <dl className="mt-4 grid grid-cols-[auto,1fr] gap-x-4 gap-y-1 rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-sm">
          {attrs.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-slate-500">{k}</dt>
              <dd className="min-w-0 break-words text-slate-300">
                {typeof v === "object" ? JSON.stringify(v) : String(v)}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {links.length > 0 && (
        <div className="mt-4">
          <h2 className="mb-1 text-sm font-medium text-slate-400">Links</h2>
          <ul className="space-y-1 text-sm">
            {links.map(([k, v]) => (
              <li key={k}>
                <a href={v} target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">
                  {k}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-2">
        {item.status === "needs_review" && (
          <>
            <button
              onClick={() => act(() => api.approve(item.id))}
              className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium"
            >
              Approve
            </button>
            <button
              onClick={() => act(() => api.reject(item.id), true)}
              className="rounded bg-rose-700 px-3 py-1.5 text-sm font-medium"
            >
              Reject
            </button>
          </>
        )}
        <button
          onClick={() => act(() => api.reprocess(item.id))}
          className="rounded border border-slate-700 px-3 py-1.5 text-sm"
        >
          Reprocess
        </button>
        <button
          onClick={() => {
            if (confirm("Delete this item?")) act(() => api.remove(item.id), true);
          }}
          className="rounded border border-rose-800 px-3 py-1.5 text-sm text-rose-300"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
