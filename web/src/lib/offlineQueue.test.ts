import { beforeEach, describe, expect, it } from "vitest";
import { _resetDbHandle } from "./offlineDb";
import {
  _resetForTests,
  enqueue,
  isPaused,
  listCounts,
  recentIssues,
  registerExecutors,
  replay,
} from "./offlineQueue";

function resp(status: number): Response {
  return { ok: status >= 200 && status < 300, status } as Response;
}

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
  _resetForTests();
});

describe("offlineQueue", () => {
  it("groups pending entries by type", async () => {
    await enqueue("approve", { id: "1" });
    await enqueue("approve", { id: "2" });
    await enqueue("reject", { id: "3" });
    expect(await listCounts()).toEqual({ approve: 2, reject: 1 });
  });

  it("replay(): success dequeues the entry", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({ approve: async () => resp(200) });
    await replay();
    expect(await listCounts()).toEqual({});
  });

  it("replay(): a network error stops the round and preserves the queue", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({
      approve: async () => {
        throw new TypeError("Failed to fetch");
      },
    });
    await replay();
    expect(await listCounts()).toEqual({ approve: 1 });
  });

  it("replay(): a 401 pauses the queue and preserves it", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({ approve: async () => resp(401) });
    await replay();
    expect(await listCounts()).toEqual({ approve: 1 });
    expect(isPaused()).toBe(true);
  });

  it("replay(): a 409 conflict drops the entry and logs an issue", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({ approve: async () => resp(409) });
    await replay();
    expect(await listCounts()).toEqual({});
    expect(recentIssues()).toHaveLength(1);
    expect(recentIssues()[0].message).toContain("409");
  });

  it("replay(): a 500 stops the round without dropping the entry", async () => {
    await enqueue("approve", { id: "1" });
    registerExecutors({ approve: async () => resp(500) });
    await replay();
    expect(await listCounts()).toEqual({ approve: 1 });
    expect(recentIssues()).toHaveLength(0);
  });

  it("replay(): processes multiple queued entries in order", async () => {
    const calls: string[] = [];
    await enqueue("approve", { id: "1" });
    await enqueue("reject", { id: "2" });
    registerExecutors({
      approve: async () => {
        calls.push("approve");
        return resp(200);
      },
      reject: async () => {
        calls.push("reject");
        return resp(200);
      },
    });
    await replay();
    expect(calls).toEqual(["approve", "reject"]);
    expect(await listCounts()).toEqual({});
  });
});
