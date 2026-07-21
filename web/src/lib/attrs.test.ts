import { describe, expect, it } from "vitest";
import { attrRows, compactNum, formatScalar, humanizeKey, linkKeyLabel, linkLabel, metaLine } from "./attrs";

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

describe("attrRows key-facts", () => {
  it("renders only curated facts as labeled chips, hides everything else", () => {
    const rows = attrRows({
      type: "show", rating: 7.8, year: "2026", runtime: 42,
      cast: ["Annette Bening", "Someone Else"],
      provider: ["Apple TV+"], network: ["Apple TV+"], genres: ["Drama"],
      tmdb_id: 220000, apple_original: true, _enrich_incomplete: "x",
    });
    const byKey = Object.fromEntries(rows.map((r) => [r.key, r]));

    expect(byKey.cast.label).toBe("Cast");
    expect(byKey.provider.label).toBe("Where to watch");
    expect(byKey.network.label).toBe("Network");
    expect(byKey.genres.label).toBe("Genres");

    // meta-line + internal + noise keys never appear as rows
    for (const k of ["rating", "year", "runtime", "type", "tmdb_id", "apple_original", "_enrich_incomplete"]) {
      expect(byKey[k]).toBeUndefined();
    }
  });
});

describe("metaLine", () => {
  it("assembles known facts, skipping unknowns", () => {
    expect(metaLine({ type: "show", attributes: { year: "2026", runtime: 42, rating: 7.8 } }))
      .toBe("2026 · 42 min · 7.8 ★ · Show");
    expect(metaLine({ type: "movie", attributes: {} })).toBe("Movie");
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
