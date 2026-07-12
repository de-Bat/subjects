import { useEffect, useState } from "react";
import { api, getApiBase, getToken, SettingsPayload, setApiBase, setToken } from "../lib/api";

export default function Settings() {
  const [base, setBase] = useState(getApiBase());
  const [token, setTok] = useState(getToken());
  const [data, setData] = useState<SettingsPayload | null>(null);
  const [patch, setPatch] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);

  function load() {
    api.getSettings().then(setData).catch((e) => setMsg(String(e)));
  }
  useEffect(load, []);

  function saveLocal() {
    setApiBase(base);
    setToken(token);
    setMsg("Saved connection. Reloading…");
    setTimeout(() => location.reload(), 400);
  }

  async function saveServer() {
    try {
      await api.updateSettings(patch);
      setPatch({});
      setMsg("Server settings saved.");
      load();
    } catch (e) {
      setMsg(String(e));
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
        <h2 className="mb-2 font-medium">Connection (this device)</h2>
        <label className="block text-xs text-slate-500">API base URL (blank = same origin)</label>
        <input
          value={base}
          onChange={(e) => setBase(e.target.value)}
          placeholder="http://192.168.1.10:8000"
          className="mb-2 w-full rounded bg-slate-950 px-2 py-1.5 text-sm outline-none"
        />
        <label className="block text-xs text-slate-500">Bearer token (APP_TOKEN)</label>
        <input
          value={token}
          onChange={(e) => setTok(e.target.value)}
          type="password"
          className="mb-3 w-full rounded bg-slate-950 px-2 py-1.5 text-sm outline-none"
        />
        <button onClick={saveLocal} className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium">
          Save connection
        </button>
      </section>

      {data && (
        <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
          <h2 className="mb-1 font-medium">AI / server settings</h2>
          <p className="mb-3 text-xs text-slate-500">
            Provider: <span className="text-slate-300">{data.ai_provider}</span>. Overrides persist in the DB;
            blank falls back to the env default.
          </p>
          <div className="space-y-2">
            {data.editable_keys.map((k) => {
              const val = patch[k] ?? data.effective[k] ?? "";
              const isKey = /key|token|secret/i.test(k);
              return (
                <div key={k} className="grid grid-cols-[minmax(0,1fr),2fr] items-center gap-2">
                  <label className="truncate text-sm text-slate-400" title={k}>
                    {k}
                    {isKey && data.keys_present[k] && <span className="ml-1 text-emerald-400">●</span>}
                  </label>
                  <input
                    value={isKey && !(k in patch) ? "" : String(val)}
                    placeholder={isKey && data.keys_present[k] ? "•••• set" : data.defaults[k] || ""}
                    type={isKey ? "password" : "text"}
                    onChange={(e) => setPatch((p) => ({ ...p, [k]: e.target.value }))}
                    className="rounded bg-slate-950 px-2 py-1.5 text-sm outline-none"
                  />
                </div>
              );
            })}
          </div>
          <button
            onClick={saveServer}
            disabled={Object.keys(patch).length === 0}
            className="mt-3 rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium disabled:opacity-40"
          >
            Save server settings
          </button>
        </section>
      )}

      {msg && <p className="rounded bg-slate-800 p-2 text-sm text-slate-300">{msg}</p>}
    </div>
  );
}
