// SSE subscription to /api/events. Reconnects automatically. Token passed as query
// param because EventSource can't set headers.
import { getApiBase, getToken } from "./api";

export interface ItemEvent {
  event: string; // item.created | item.updated
  item_id: string;
  stage?: string;
  status?: string;
}

export function subscribeEvents(onEvent: (e: ItemEvent) => void): () => void {
  let es: EventSource | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    const token = encodeURIComponent(getToken());
    es = new EventSource(`${getApiBase()}/api/events?token=${token}`);
    es.addEventListener("item", (ev) => {
      try {
        onEvent(JSON.parse((ev as MessageEvent).data));
      } catch {
        /* ignore malformed frames */
      }
    });
    es.onerror = () => {
      es?.close();
      if (!closed) setTimeout(connect, 3000);
    };
  }

  connect();
  return () => {
    closed = true;
    es?.close();
  };
}
