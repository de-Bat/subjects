import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetDbHandle } from "./offlineDb";
import { _resetForTests as resetQueue } from "./offlineQueue";
import { _resetForTests as resetConnectivity } from "./connectivity";
import { api } from "./api";

async function wipeDb(): Promise<void> {
  _resetDbHandle();
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.deleteDatabase("subjects-offline");
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    req.onblocked = () => resolve();
  });
}

beforeEach(async () => {
  await wipeDb();
  resetQueue();
  resetConnectivity();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api offline fallback", () => {
  it("getItem() falls back to the cache on a network error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "1", title: "Cached" }), { status: 200 }),
      )
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await api.getItem("1"); // primes the cache
    const item = await api.getItem("1"); // network fails -> cache fallback
    expect(item.title).toBe("Cached");
  });

  it("approve() enqueues and returns an optimistically patched item when offline", async () => {
    const listed = new Response(
      JSON.stringify([{ id: "1", title: "T", status: "needs_review" }]),
      { status: 200 },
    );
    const fetchMock = vi.fn().mockResolvedValueOnce(listed).mockRejectedValueOnce(new TypeError("down"));
    vi.stubGlobal("fetch", fetchMock);

    await api.listItems(); // primes the /api/items cache
    const patched = await api.approve("1");
    expect(patched.status).toBe("enriched");
  });

  it("ingestJSON() enqueues a capture and returns a synthetic id when offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    const result = await api.ingestJSON({ url: "https://example.com" });
    expect(result.id).toMatch(/^local:/);
  });

  it("getItem() falls back to a detail entry backfilled from listItems(), even though getItem was never called directly before", async () => {
    const listed = new Response(
      JSON.stringify([{ id: "42", title: "From list" }]),
      { status: 200 },
    );
    const fetchMock = vi.fn().mockResolvedValueOnce(listed).mockRejectedValueOnce(new TypeError("down"));
    vi.stubGlobal("fetch", fetchMock);

    await api.listItems(); // primes /api/items and should backfill /api/items/42
    const item = await api.getItem("42"); // network fails -> cache fallback
    expect(item.title).toBe("From list");
  });
});
