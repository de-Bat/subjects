import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, Item, mediaUrl } from "../lib/api";
import { subscribeEvents } from "../lib/sse";
import StatusBadge from "../components/StatusBadge";
import ProcessingProgress from "../components/ProcessingProgress";
import Provenance from "../components/Provenance";
import { readProvenance } from "../lib/provenance";
import { attrRows, linkKeyLabel, linkLabel } from "../lib/attrs";

function IconBox({ url, seed }: { url?: string | null; seed: string }) {
  if (url) return <img src={url} alt="" className="mt-1 h-10 w-10 shrink-0 rounded object-cover" />;
  const ch = (seed.trim()[0] || "?").toUpperCase();
  return (
    <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded bg-slate-700 text-lg font-semibold text-slate-200">
      {ch}
    </div>
  );
}

function LinkPill({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center rounded-full border border-indigo-700/60 bg-indigo-900/30 px-3 py-1 text-xs font-medium text-indigo-300 hover:bg-indigo-900/60"
    >
      {label} ↗
    </a>
  );
}

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
  const rows = attrRows(item.attributes || {});
  const links = Object.entries(item.links || {}).filter(([, v]) => !!v) as [string, string][];

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
        <IconBox url={item.icon_url} seed={item.title || item.type} />
        <div className="min-w-0">
          <h1 className="text-xl font-semibold">{item.title || "Untitled"}</h1>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {item.canonical_url && <LinkPill href={item.canonical_url} label={linkLabel(item.canonical_url)} />}
            {links.map(([k, v]) => (
              <LinkPill key={k} href={v} label={linkKeyLabel(k)} />
            ))}
          </div>
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

      {rows.length > 0 && (
        <dl className="mt-4 grid grid-cols-[auto,1fr] items-baseline gap-x-4 gap-y-2 rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-sm">
          {rows.map((r) => (
            <div key={r.key} className="contents">
              <dt className="text-slate-500">{r.label}</dt>
              <dd className="min-w-0 break-words text-slate-300">
                {r.kind === "chips" ? (
                  <span className="flex flex-wrap gap-1.5">
                    {r.chips!.map((c) => (
                      <span key={c} className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-300">
                        {c}
                      </span>
                    ))}
                  </span>
                ) : (
                  r.text
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}

      <Provenance steps={readProvenance(item.attributes || {})} />

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
