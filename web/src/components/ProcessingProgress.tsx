import { STAGES, progressState } from "../lib/progress";

export default function ProcessingProgress({ status, stage }: { status: string; stage?: string }) {
  const { visible, filledUpTo, error } = progressState(status, stage);
  if (!visible) return null;
  return (
    <div className="mb-4">
      <div className="mb-1 flex gap-1">
        {STAGES.map((s, i) => {
          const filled = i <= filledUpTo;
          const current = i === filledUpTo + 1;
          return (
            <div
              key={s}
              title={s}
              className={
                "h-1.5 flex-1 rounded-full transition-colors " +
                (error && filled ? "bg-red-500" : filled ? "bg-indigo-500" : "bg-slate-800") +
                (current ? " animate-pulse bg-indigo-700" : "")
              }
            />
          );
        })}
      </div>
      <p className="text-xs text-slate-500">
        Processing… {stage ? `(${stage})` : ""}
      </p>
    </div>
  );
}
