import { ProvStep } from "../lib/provenance";

export default function Provenance({ steps }: { steps: ProvStep[] }) {
  if (steps.length === 0) return null;
  return (
    <details className="mt-4 rounded-lg border border-slate-800 bg-slate-900/50 p-3">
      <summary className="cursor-pointer text-sm font-medium text-slate-300">
        How I got there
      </summary>
      <ol className="mt-2 space-y-2 text-sm">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-2">
            <span className="mt-0.5 text-xs text-slate-600">{i + 1}</span>
            <div className="min-w-0">
              <span className="mr-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                {s.stage}
              </span>
              <span className="text-slate-300">{s.summary}</span>
              {s.detail && (
                <details className="mt-0.5">
                  <summary className="cursor-pointer text-[11px] text-slate-600">
                    Technical details
                  </summary>
                  <div className="text-xs text-slate-500">{s.detail}</div>
                </details>
              )}
            </div>
          </li>
        ))}
      </ol>
    </details>
  );
}
