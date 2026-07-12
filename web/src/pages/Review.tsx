import { useEffect, useState } from "react";
import { api, Item } from "../lib/api";
import { subscribeEvents } from "../lib/sse";
import ItemCard from "../components/ItemCard";

// Review queue: low-confidence / ambiguous items the pipeline flagged needs_review.
export default function Review() {
  const [items, setItems] = useState<Item[]>([]);

  function load() {
    api.listItems({ status: "needs_review" }).then(setItems).catch(() => {});
  }

  useEffect(() => {
    load();
    return subscribeEvents(() => load());
  }, []);

  async function approve(id: string) {
    await api.approve(id);
    load();
  }
  async function reject(id: string) {
    await api.reject(id);
    load();
  }

  return (
    <div className="space-y-2">
      {items.length === 0 && (
        <p className="py-12 text-center text-sm text-slate-500">Nothing to review. Inbox is clean.</p>
      )}
      {items.map((it) => (
        <div key={it.id} className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <ItemCard item={it} />
          </div>
          <div className="flex shrink-0 flex-col gap-1">
            <button
              onClick={() => approve(it.id)}
              className="rounded bg-emerald-600 px-2 py-1 text-xs font-medium"
            >
              Approve
            </button>
            <button onClick={() => reject(it.id)} className="rounded bg-rose-700 px-2 py-1 text-xs font-medium">
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
