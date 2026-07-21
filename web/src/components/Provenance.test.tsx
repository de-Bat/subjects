import { describe, expect, it } from "vitest";
import Provenance from "./Provenance";

describe("Provenance", () => {
  it("exports a default component function", () => {
    // @testing-library/react is not installed in this project; per task-8-brief.md
    // fallback, we assert the module shape instead of rendering.
    expect(typeof Provenance).toBe("function");
  });
});
