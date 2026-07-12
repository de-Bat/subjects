import { getApiBase } from "./config";

export type ConnectivityListener = (online: boolean) => void;

const listeners = new Set<ConnectivityListener>();
let online = true;
let timer: ReturnType<typeof setInterval> | null = null;

function setOnline(next: boolean): void {
  if (next === online) return;
  online = next;
  listeners.forEach((fn) => fn(online));
}

export function isOnline(): boolean {
  return online;
}

export function subscribe(fn: ConnectivityListener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export async function ping(): Promise<boolean> {
  const ctrl = new AbortController();
  const timeout = setTimeout(() => ctrl.abort(), 4000);
  try {
    const resp = await fetch(`${getApiBase()}/api/health`, { cache: "no-store", signal: ctrl.signal });
    setOnline(resp.ok);
    return resp.ok;
  } catch {
    setOnline(false);
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

export function startPolling(intervalMs = 12000): void {
  if (timer) return;
  void ping();
  timer = setInterval(() => void ping(), intervalMs);
}

export function stopPolling(): void {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

export function notifyFetchFailed(): void {
  void ping();
}

// Test-only: reset module-level state between tests.
export function _resetForTests(): void {
  stopPolling();
  online = true;
  listeners.clear();
}
