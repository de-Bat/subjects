"""Stage 2 — extract signals from url / image / text inputs."""
import logging
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from ..ai import prompts
from ..ai.provider import complete_json, get_provider
from ..ai.vision import extract_image_signals
from ..models.schemas import Signals, VisionResult
from .classify import classify_source, find_url, source_url

log = logging.getLogger(__name__)

FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SubjectsBot/1.0; +https://github.com/subjects)",
    "Accept": "text/html,application/xhtml+xml",
}
FETCH_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


def parse_meta(html: str, base_url: str) -> tuple[dict, list, str | None]:
    """Open Graph / Twitter Card props, JSON-LD blocks, and <link rel=canonical>."""
    soup = BeautifulSoup(html, "html.parser")
    og: dict = {}
    for meta in soup.find_all("meta"):
        key = meta.get("property") or meta.get("name") or ""
        content = meta.get("content")
        if not content:
            continue
        if key.startswith(("og:", "twitter:", "article:")):
            og.setdefault(key, content)
        elif key == "description":
            og.setdefault("description", content)
    if title_tag := soup.find("title"):
        og.setdefault("page_title", title_tag.get_text(strip=True))
    if icon := soup.find("link", rel=lambda v: v and "icon" in v):
        if href := icon.get("href"):
            og.setdefault("icon", str(httpx.URL(base_url).join(href)))

    canonical = None
    if link := soup.find("link", rel="canonical"):
        canonical = link.get("href")

    jsonld: list = []
    try:
        import extruct

        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        jsonld = data.get("json-ld", [])
    except Exception as exc:  # extruct chokes on malformed markup; signals stay usable without it
        log.warning("json-ld extraction failed: %s", exc)

    return og, jsonld, canonical


async def fetch_oembed(client: httpx.AsyncClient, html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("link", type="application/json+oembed")
    if not link or not link.get("href"):
        return {}
    try:
        resp = await client.get(str(httpx.URL(base_url).join(link["href"])), headers=FETCH_HEADERS)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


async def extract_url_signals(url: str) -> Signals:
    signals = Signals(input_type="url", url=url, canonical_url=url)
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, headers=FETCH_HEADERS)
        resp.raise_for_status()
        final_url = str(resp.url)
        html = resp.text
        og, jsonld, canonical = parse_meta(html, final_url)
        signals.og = og
        signals.jsonld = jsonld
        signals.canonical_url = canonical or final_url
        signals.oembed = await fetch_oembed(client, html, final_url)

    try:
        import trafilatura

        body = trafilatura.extract(html, url=final_url)
        if body:
            signals.body_text = body[:8000]
    except Exception as exc:
        log.warning("trafilatura failed: %s", exc)
    return signals


async def extract_image_path_signals(image_path: str) -> Signals:
    image = Path(image_path).read_bytes()
    vision = await extract_image_signals(image)
    signals = Signals(input_type="image", image_path=image_path, vision=vision)
    # A screenshot with a readable URL should converge with the pasted-URL path.
    if vision.visible_url:
        url = vision.visible_url
        if not url.startswith("http"):
            url = "https://" + url
        signals.url = url
        signals.canonical_url = url
    return signals


async def extract_text_signals(text: str, title: str | None = None) -> Signals:
    signals = Signals(input_type="text", text=text, title=title)
    if url := find_url(text):
        signals.url = url
    vision = await complete_json(
        get_provider(),
        VisionResult,
        f"Text:\n{text[:4000]}",
        system=prompts.TEXT_SIGNALS_SYSTEM,
    )
    signals.vision = vision or VisionResult(ocr_text=text)
    if not signals.vision.ocr_text:
        signals.vision.ocr_text = text
    return signals


async def extract(source: dict) -> Signals:
    """Route the raw ingest payload to the right extractor."""
    input_type = classify_source(source)
    if input_type == "image":
        signals = await extract_image_path_signals(source["media_path"])
    elif input_type == "url":
        signals = await extract_url_signals(source_url(source))
    else:
        signals = await extract_text_signals(source.get("text") or "", source.get("title"))
    if source.get("title") and not signals.title:
        signals.title = source["title"]
    if source.get("text") and not signals.text:
        signals.text = source["text"]
    return signals
