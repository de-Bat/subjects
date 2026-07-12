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
