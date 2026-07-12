/// <reference lib="webworker" />
// Service worker: Workbox precache + Android Web Share Target handler (spec Section 5).
// Intercepts POST /share-target, forwards the FormData to /api/ingest, then redirects
// the client to the new item's view.
import { precacheAndRoute } from "workbox-precaching";

declare const self: ServiceWorkerGlobalScope;

precacheAndRoute(self.__WB_MANIFEST || []);

// The bearer token is stashed by the app into a Cache entry the SW can read,
// since the SW has no access to localStorage.
const TOKEN_CACHE = "subjects-config";
const TOKEN_URL = "/__subjects_token";

async function readToken(): Promise<string> {
  const cache = await caches.open(TOKEN_CACHE);
  const resp = await cache.match(TOKEN_URL);
  return resp ? (await resp.text()) : "";
}

self.addEventListener("fetch", (event: FetchEvent) => {
  const requestUrl = new URL(event.request.url);
  if (event.request.method === "POST" && requestUrl.pathname === "/share-target") {
    event.respondWith(handleShare(event.request));
  }
});

async function handleShare(request: Request): Promise<Response> {
  const formData = await request.formData();
  const forward = new FormData();
  for (const key of ["title", "text", "url"]) {
    const v = formData.get(key);
    if (v) forward.append(key, v);
  }
  const media = formData.get("media");
  if (media && media instanceof File) forward.append("media", media, media.name);

  const token = await readToken();
  try {
    const resp = await fetch("/api/ingest", {
      method: "POST",
      headers: { "X-Subjects-Channel": "android-share", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: forward,
    });
    if (resp.ok) {
      const { id } = await resp.json();
      return Response.redirect(`/item/${id}`, 303);
    }
  } catch {
    /* fall through to inbox */
  }
  return Response.redirect("/", 303);
}
