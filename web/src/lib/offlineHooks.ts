import { useEffect, useState } from "react";
import { isOnline, subscribe } from "./connectivity";
import { isPaused, listCounts, recentIssues, subscribeCounts, type QueueCounts } from "./offlineQueue";

export function useOnlineStatus(): boolean {
  const [online, setOnlineState] = useState(isOnline());
  useEffect(() => subscribe(setOnlineState), []);
  return online;
}

export interface QueueStatus {
  counts: QueueCounts;
  total: number;
  issues: string[];
  paused: boolean;
}

export function useQueueCounts(): QueueStatus {
  const [counts, setCounts] = useState<QueueCounts>({});
  const [issues, setIssues] = useState<string[]>([]);
  const [paused, setPaused] = useState(isPaused());

  useEffect(() => {
    async function refresh() {
      setCounts(await listCounts());
      setIssues(recentIssues().map((i) => i.message));
      setPaused(isPaused());
    }
    refresh();
    return subscribeCounts(refresh);
  }, []);

  const total = Object.values(counts).reduce((sum, n) => sum + (n || 0), 0);
  return { counts, total, issues, paused };
}
