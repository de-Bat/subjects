import { describe, expect, it } from "vitest";
import { STAGES, progressState, stageIndex } from "./progress";

describe("progress helpers", () => {
  it("maps stages to indices", () => {
    expect(stageIndex("classify")).toBe(0);
    expect(stageIndex("finalize")).toBe(STAGES.length - 1);
    expect(stageIndex("nope")).toBe(-1);
    expect(stageIndex(undefined)).toBe(-1);
  });

  it("is visible and mid-fill while processing", () => {
    const s = progressState("processing", "resolve");
    expect(s.visible).toBe(true);
    expect(s.filledUpTo).toBe(stageIndex("resolve"));
    expect(s.error).toBe(false);
    expect(s.done).toBe(false);
  });

  it("pending with no stage is visible at start", () => {
    const s = progressState("pending", undefined);
    expect(s.visible).toBe(true);
    expect(s.filledUpTo).toBe(-1);
  });

  it("terminal enriched status is done and fully filled, not visible", () => {
    const s = progressState("enriched", "finalize");
    expect(s.visible).toBe(false);
    expect(s.done).toBe(true);
    expect(s.filledUpTo).toBe(STAGES.length - 1);
  });

  it("error status flags error", () => {
    const s = progressState("error", "enrich");
    expect(s.error).toBe(true);
    expect(s.visible).toBe(false);
  });
});
