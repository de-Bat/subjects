const STYLES: Record<string, string> = {
  pending: "bg-amber-900/40 text-amber-300",
  processing: "bg-sky-900/40 text-sky-300",
  enriched: "bg-emerald-900/40 text-emerald-300",
  needs_review: "bg-fuchsia-900/40 text-fuchsia-300",
  rejected: "bg-rose-900/40 text-rose-300",
  duplicate: "bg-slate-800 text-slate-400",
  error: "bg-red-900/50 text-red-300",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = STYLES[status] || "bg-slate-800 text-slate-300";
  return (
    <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls}`}>
      {status.replace("_", " ")}
    </span>
  );
}
