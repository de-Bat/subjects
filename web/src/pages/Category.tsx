import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Item, TreeNode } from "../lib/api";
import ItemCard from "../components/ItemCard";

// Category tree on the left of the intent, item list for the selected category.
function TreeItem({ node, active }: { node: TreeNode; active?: string }) {
  const on = active === node.name;
  return (
    <li>
      <Link
        to={`/categories/${encodeURIComponent(node.name)}`}
        className={`flex items-center justify-between rounded px-2 py-1 text-sm ${
          on ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"
        }`}
      >
        <span>{node.name}</span>
        <span className="text-xs text-slate-600">{node.count}</span>
      </Link>
      {node.children.length > 0 && (
        <ul className="ml-3 border-l border-slate-800 pl-2">
          {node.children.map((c) => (
            <TreeItem key={c.id} node={c} active={active} />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function CategoryPage() {
  const { name } = useParams();
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    api.tree().then(setTree).catch(() => {});
  }, []);

  useEffect(() => {
    if (name) api.listItems({ category: name }).then(setItems).catch(() => setItems([]));
    else setItems([]);
  }, [name]);

  return (
    <div className="grid grid-cols-[minmax(140px,220px),1fr] gap-4">
      <aside>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Categories</h2>
        <ul className="space-y-0.5">
          {tree.length === 0 && <li className="text-sm text-slate-600">None yet</li>}
          {tree.map((n) => (
            <TreeItem key={n.id} node={n} active={name} />
          ))}
        </ul>
      </aside>
      <section className="min-w-0 space-y-2">
        {!name && <p className="py-12 text-center text-sm text-slate-500">Pick a category.</p>}
        {name && items.length === 0 && (
          <p className="py-12 text-center text-sm text-slate-500">No items in “{name}”.</p>
        )}
        {items.map((it) => (
          <ItemCard key={it.id} item={it} />
        ))}
      </section>
    </div>
  );
}
