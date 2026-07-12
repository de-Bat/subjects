import { queueAdd, queueAll, queueDelete, type QueueEntry, type QueueType } from "./offlineDb";
import { subscribe as subscribeConnectivity } from "./connectivity";

export type QueueCounts = Partial<Record<QueueType, number>>;

export interface IssueNote {
  message: string;
  at: number;
}

export type Executor = (payload: unknown) => Promise<Response>;

const MAX_ISSUES = 20;
let issues: IssueNote[] = [];
let replaying = false;
let paused = false;
let executors: Partial<Record<QueueType, Executor>> = {};

type Listener = () => void;
const countsListeners = new Set<Listener>();

function notifyCountsChanged(): void {
  countsListeners.forEach((fn) => fn());
}

export function registerExecutors(map: Partial<Record<QueueType, Executor>>): void {
  executors = { ...executors, ...map };
}

export async function enqueue(type: QueueType, payload: unknown): Promise<number> {
  const id = await queueAdd(type, payload);
  notifyCountsChanged();
  return id;
}

export async function listCounts(): Promise<QueueCounts> {
  const all = await queueAll();
  const counts: QueueCounts = {};
  for (const entry of all) {
    counts[entry.type] = (counts[entry.type] || 0) + 1;
  }
  return counts;
}

export function recentIssues(): IssueNote[] {
  return issues.slice();
}

export function isPaused(): boolean {
  return paused;
}

export function subscribeCounts(fn: Listener): () => void {
  countsListeners.add(fn);
  return () => countsListeners.delete(fn);
}

function addIssue(message: string): void {
  issues.push({ message, at: Date.now() });
  if (issues.length > MAX_ISSUES) issues.shift();
}

export async function replay(): Promise<void> {
  if (replaying) return;
  replaying = true;
  try {
    for (;;) {
      const all: QueueEntry[] = await queueAll();
      if (all.length === 0) {
        paused = false;
        return;
      }
      const entry = all[0];
      const exec = executors[entry.type];
      if (!exec) {
        await queueDelete(entry.id);
        notifyCountsChanged();
        continue;
      }
      let response: Response;
      try {
        response = await exec(entry.payload);
      } catch {
        return; // network error: stop this round, still offline
      }
      if (response.ok) {
        paused = false;
        await queueDelete(entry.id);
        notifyCountsChanged();
        continue;
      }
      if (response.status === 401) {
        paused = true;
        return;
      }
      if (response.status >= 500) {
        return; // transient server issue: stop the round, keep the entry
      }
      addIssue(`${entry.type} — skipped (HTTP ${response.status})`);
      await queueDelete(entry.id);
      notifyCountsChanged();
    }
  } finally {
    replaying = false;
  }
}

subscribeConnectivity((online) => {
  if (online) void replay();
});

// Test-only: reset module-level state between tests.
export function _resetForTests(): void {
  issues = [];
  replaying = false;
  paused = false;
  executors = {};
}
