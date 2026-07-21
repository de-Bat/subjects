import { describe, expect, it } from "vitest";
import { attrRows, compactNum, formatScalar, humanizeKey, linkKeyLabel, linkLabel } from "./attrs";

describe("compactNum", () => {
  it("abbreviates thousands and millions", () => {
    expect(compactNum(1200)).toBe("1.2k");
    expect(compactNum(230000)).toBe("230k");
    expect(compactNum(1_500_000)).toBe("1.5M");
    expect(compactNum(48)).toBe("48");
  });
});

describe("humanizeKey", () => {
  it("title-cases and special-cases keys", () => {
    expect(humanizeKey("apple_original")).toBe("Apple Original");
    expect(humanizeKey("tmdb_id")).toBe("TMDB ID");
    expect(humanizeKey("release_date")).toBe("Release Date");
    expect(humanizeKey("rating")).toBe("Rating");
  });
});

describe("formatScalar", () => {
  it("formats rating, runtime, and compact counts", () => {
    expect(formatScalar("rating", 7.8)).toBe("7.8 ★");
    expect(formatScalar("runtime", 52)).toBe("52 min");
    expect(formatScalar("stars", 230000)).toBe("230k");
    expect(formatScalar("year", "2026")).toBe("2026");
    expect(formatScalar("archived", false)).toBe("No");
  });
});

describe("attrRows", () => {
  it("renders arrays as chips and scalars as formatted text, no JSON", () => {
    const rows = attrRows({
      type: "show",
      rating: 7.8,
      cast: ["Annette Bening", "Someone Else"],
      provider: ["Apple TV+"],
      apple_original: true,
      tmdb_id: 220000,
      year: "2026",
      network: [],
      note: null,
    });
    const byKey = Object.fromEntries(rows.map((r) => [r.key, r]));

    // hidden / empty / internal keys dropped
    expect(byKey.type).toBeUndefined();
    expect(byKey.tmdb_id).toBeUndefined();
    expect(byKey.network).toBeUndefined(); // empty array
    expect(byKey.note).toBeUndefined(); // null

    // arrays -> chips
    expect(byKey.cast.kind).toBe("chips");
    expect(byKey.cast.chips).toEqual(["Annette Bening", "Someone Else"]);

    // scalars -> formatted text
    expect(byKey.rating.kind).toBe("text");
    expect(byKey.rating.text).toBe("7.8 ★");

    // true boolean shown, no raw JSON anywhere
    expect(byKey.apple_original.text).toBe("Yes");
    for (const r of rows) {
      const s = r.text ?? "";
      expect(s.includes("{")).toBe(false);
      expect(s.includes("[")).toBe(false);
    }
  });

  it("drops _-prefixed engine metadata and false flags", () => {
    const rows = attrRows({ _provenance: [{ stage: "x" }], archived: false, language: "Python" });
    const keys = rows.map((r) => r.key);
    expect(keys).not.toContain("_provenance");
    expect(keys).not.toContain("archived");
    expect(keys).toContain("language");
  });
});

describe("linkLabel / linkKeyLabel", () => {
  it("labels canonical URLs by host", () => {
    expect(linkLabel("https://www.themoviedb.org/tv/220000")).toBe("View on TMDB");
    expect(linkLabel("https://www.imdb.com/title/tt9999999/")).toBe("View on IMDb");
    expect(linkLabel("https://github.com/facebook/react")).toBe("View on GitHub");
    expect(linkLabel("https://example.com/x")).toBe("View on example.com");
    expect(linkLabel("not a url")).toBe("Open link");
  });

  it("labels link-dict keys", () => {
    expect(linkKeyLabel("trailer")).toBe("Watch trailer");
    expect(linkKeyLabel("repo")).toBe("Repository");
    expect(linkKeyLabel("homepage")).toBe("Homepage");
  });
});
