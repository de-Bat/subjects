// MV3 service worker. Toolbar click + right-click menu "Send to Subjects".
// Grabs current tab URL + selection; optionally a visible-tab screenshot.
// POSTs to <apiBase>/api/ingest with the stored bearer token.

const DEFAULTS = { apiBase: "", token: "", screenshot: false };

async function config() {
  const c = await chrome.storage.sync.get(DEFAULTS);
  return { ...DEFAULTS, ...c };
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "send-to-subjects",
    title: "Send to Subjects",
    contexts: ["page", "selection", "link", "image"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  const url = info.linkUrl || info.srcUrl || info.pageUrl || (tab && tab.url);
  capture(tab, { url, text: info.selectionText || "" });
});

chrome.action.onClicked.addListener((tab) => {
  capture(tab, { url: tab.url, text: "" });
});

async function getSelection(tabId) {
  try {
    const [res] = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => window.getSelection().toString(),
    });
    return (res && res.result) || "";
  } catch {
    return "";
  }
}

function dataUrlToBlob(dataUrl) {
  const [head, b64] = dataUrl.split(",");
  const mime = head.match(/data:(.*?);/)[1];
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return new Blob([arr], { type: mime });
}

async function capture(tab, { url, text }) {
  const cfg = await config();
  if (!cfg.apiBase || !cfg.token) {
    notify("Not configured", "Set the API base URL and token in extension options.");
    chrome.runtime.openOptionsPage();
    return;
  }

  if (!text && tab && tab.id != null) text = await getSelection(tab.id);

  const fd = new FormData();
  if (url) fd.append("url", url);
  if (text) fd.append("text", text);
  if (tab && tab.title) fd.append("title", tab.title);

  if (cfg.screenshot && tab && tab.windowId != null) {
    try {
      const shot = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
      fd.append("media", dataUrlToBlob(shot), "screenshot.png");
    } catch {
      /* screenshot best-effort */
    }
  }

  try {
    const resp = await fetch(`${cfg.apiBase.replace(/\/$/, "")}/api/ingest`, {
      method: "POST",
      headers: { "X-Subjects-Channel": "extension", Authorization: `Bearer ${cfg.token}` },
      body: fd,
    });
    if (resp.ok) notify("Captured", tab && tab.title ? tab.title : url || "Sent to Subjects");
    else notify("Failed", `${resp.status} ${resp.statusText}`);
  } catch (e) {
    notify("Failed", String(e));
  }
}

function notify(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icon-128.png",
    title: `Subjects — ${title}`,
    message: message || "",
  });
}
