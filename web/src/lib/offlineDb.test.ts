import { beforeEach, describe, expect, it } from "vitest";
import { cacheGet, cacheSet, queueAdd, queueAll, queueDelete, _resetDbHandle } from "./offlineDb";

async function wipe(): Promise<void> {
  _resetDbHandle();
  await new Promise<void>((resolve, reject) => {
    const req = indexedDB.deleteDatabase("subjects-offline");
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
    req.onblocked = () => resolve();
  });
}

beforeEach(wipe);

describe("offlineDb cache store", () => {
  it("returns undefined for a missing key", async () => {
    expect(await cacheGet("nope")).toBeUndefined();
  });

  it("round-trips a value", async () => {
    await cacheSet("/api/items", [{ id: "1" }]);
    const entry = await cacheGet("/api/items");
    expect(entry?.data).toEqual([{ id: "1" }]);
    expect(typeof entry?.cachedAt).toBe("number");
  });
});

describe("offlineDb queue store", () => {
  it("adds entries in FIFO order with autoincrement ids", async () => {
    const id1 = await queueAdd("approve", { id: "a" });
    const id2 = await queueAdd("reject", { id: "b" });
    expect(id2).toBeGreaterThan(id1);

    const all = await queueAll();
    expect(all.map((e) => e.type)).toEqual(["approve", "reject"]);
  });

  it("deletes an entry by id", async () => {
    const id = await queueAdd("remove", { id: "x" });
    await queueDelete(id);
    expect(await queueAll()).toEqual([]);
  });
});
