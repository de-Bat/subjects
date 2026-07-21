import { describe, expect, it } from "vitest";
import { readProvenance, visibleAttrs } from "./provenance";

describe("provenance helpers", () => {
  it("reads steps from attributes._provenance", () => {
    const steps = readProvenance({
      type: "show",
      _provenance: [
        { stage: "vision", summary: "detected instagram", detail: null },
        { stage: "why", summary: "cast matched" },
      ],
    });
    expect(steps).toHaveLength(2);
    expect(steps[0].stage).toBe("vision");
    expect(steps[1].summary).toBe("cast matched");
  });

  it("returns empty array when no provenance", () => {
    expect(readProvenance({ type: "movie" })).toEqual([]);
    expect(readProvenance({ _provenance: "garbage" } as never)).toEqual([]);
  });

  it("hides underscore-prefixed keys from the attribute table", () => {
    const attrs = visibleAttrs({ type: "show", cast: ["A"], _provenance: [1], _internal: 2 });
    const keys = attrs.map(([k]) => k);
    expect(keys).toContain("type");
    expect(keys).toContain("cast");
    expect(keys).not.toContain("_provenance");
    expect(keys).not.toContain("_internal");
  });
});
