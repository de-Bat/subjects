import { Link } from "react-router-dom";
import { Item, mediaUrl } from "../lib/api";
import StatusBadge from "./StatusBadge";
import ProcessingProgress from "./ProcessingProgress";

export default function ItemCard({ item, stage }: { item: Item; stage?: string }) {
  const thumb = mediaUrl(item);
  return (
    <Link
      to={`/item/${item.id}`}
      className="flex gap-3 rounded-lg border border-slate-800 bg-slate-900/50 p-3 transition hover:border-slate-600"
    >
      <div className="h-16 w-16 shrink-0 overflow-hidden rounded bg-slate-800">
        {thumb ? (
          <img src={thumb} alt="" className="h-full w-full object-cover" loading="lazy" />
        ) : item.icon_url ? (
          <img src={item.icon_url} alt="" className="h-full w-full object-contain p-2" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-slate-500">
            {item.type}
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {item.icon_url && <img src={item.icon_url} alt="" className="h-4 w-4 shrink-0 rounded-sm" />}
          <span className="truncate font-medium">{item.title || "Untitled"}</span>
          <StatusBadge status={item.status} />
        </div>
        {item.canonical_url && (
          <span className="block truncate text-xs text-indigo-400">{item.canonical_url}</span>
        )}
        {item.description && (
          <p className="mt-0.5 line-clamp-2 text-sm text-slate-400">{item.description}</p>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
          <span className="rounded bg-slate-800 px-1.5 py-0.5">{item.type}</span>
          {item.categories.map((c) => (
            <span key={c.id} className="rounded bg-indigo-900/40 px-1.5 py-0.5 text-indigo-300">
              {c.name}
            </span>
          ))}
          {item.tags.map((t) => (
            <span key={t.id} className="rounded bg-slate-800 px-1.5 py-0.5">
              #{t.name}
            </span>
          ))}
          {item.confidence != null && <span>· {(item.confidence * 100).toFixed(0)}%</span>}
        </div>
        <ProcessingProgress status={item.status} stage={stage} compact />
      </div>
    </Link>
  );
}
