export const STAGES = [
  "classify", "extract", "resolve", "enrich", "categorize", "dedup", "finalize",
];

const TERMINAL = new Set(["enriched", "needs_review", "duplicate", "rejected", "error", "failed"]);
const ERROR = new Set(["error", "failed"]);

export function stageIndex(stage?: string): number {
  return stage ? STAGES.indexOf(stage) : -1;
}

export function progressState(status: string, stage?: string) {
  const terminal = TERMINAL.has(status);
  const error = ERROR.has(status);
  return {
    visible: !terminal,
    filledUpTo: terminal && !error ? STAGES.length - 1 : stageIndex(stage),
    error,
    done: terminal && !error,
  };
}
