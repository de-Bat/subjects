const DEFAULTS = { apiBase: "", token: "", screenshot: false };

async function load() {
  const c = await chrome.storage.sync.get(DEFAULTS);
  document.getElementById("apiBase").value = c.apiBase || "";
  document.getElementById("token").value = c.token || "";
  document.getElementById("screenshot").checked = !!c.screenshot;
}

document.getElementById("save").addEventListener("click", async () => {
  await chrome.storage.sync.set({
    apiBase: document.getElementById("apiBase").value.trim(),
    token: document.getElementById("token").value.trim(),
    screenshot: document.getElementById("screenshot").checked,
  });
  const s = document.getElementById("status");
  s.textContent = "Saved.";
  setTimeout(() => (s.textContent = ""), 1500);
});

load();
