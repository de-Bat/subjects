import { useEffect } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { startPolling } from "./lib/connectivity";
import SyncStatusPill from "./components/SyncStatusPill";
import Inbox from "./pages/Inbox";
import ItemPage from "./pages/Item";
import CategoryPage from "./pages/Category";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import SearchPage from "./pages/Search";

const tabs = [
  { to: "/", label: "Inbox", end: true },
  { to: "/categories", label: "Categories" },
  { to: "/review", label: "Review" },
  { to: "/search", label: "Search" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  useEffect(() => {
    startPolling();
  }, []);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <nav className="mx-auto flex max-w-3xl items-center gap-1 px-4 py-3 text-sm">
          <span className="mr-3 font-semibold tracking-tight">Subjects</span>
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                `rounded px-3 py-1.5 transition ${
                  isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
          <SyncStatusPill />
        </nav>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Inbox />} />
          <Route path="/item/:id" element={<ItemPage />} />
          <Route path="/categories" element={<CategoryPage />} />
          <Route path="/categories/:name" element={<CategoryPage />} />
          <Route path="/review" element={<Review />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
