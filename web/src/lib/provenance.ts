export interface ProvStep {
  stage: string;
  summary: string;
  detail?: string | null;
}

export function readProvenance(attributes: Record<string, unknown>): ProvStep[] {
  const raw = attributes?._provenance;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (s): s is ProvStep =>
      !!s && typeof s === "object" && typeof (s as ProvStep).stage === "string",
  );
}

export function visibleAttrs(attributes: Record<string, unknown>): [string, unknown][] {
  return Object.entries(attributes || {}).filter(([k]) => !k.startsWith("_"));
}
