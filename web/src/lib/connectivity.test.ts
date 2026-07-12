import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetForTests, isOnline, notifyFetchFailed, ping, subscribe } from "./connectivity";

beforeEach(() => {
  _resetForTests();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("connectivity", () => {
  it("starts online by default", () => {
    expect(isOnline()).toBe(true);
  });

  it("ping() flips offline on a rejected fetch", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const ok = await ping();
    expect(ok).toBe(false);
    expect(isOnline()).toBe(false);
  });

  it("ping() flips back online on a successful fetch", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    await ping();
    expect(isOnline()).toBe(false);

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true } as Response));
    const ok = await ping();
    expect(ok).toBe(true);
    expect(isOnline()).toBe(true);
  });

  it("notifies subscribers only when the state actually changes", async () => {
    const seen: boolean[] = [];
    const unsubscribe = subscribe((v) => seen.push(v));

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true } as Response));
    await ping(); // already online -> no change -> no notification

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    await ping(); // online -> offline -> notified

    unsubscribe();
    expect(seen).toEqual([false]);
  });

  it("notifyFetchFailed() triggers a ping", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("down"));
    vi.stubGlobal("fetch", fetchMock);
    notifyFetchFailed();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });
});
