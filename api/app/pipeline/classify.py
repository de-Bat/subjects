"""Stage 1 — classify the raw shared payload as image / url / text."""
import re

from ..models.schemas import InputType

URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def find_url(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"https?://[^\s<>\"']+", text)
    return m.group(0).rstrip(").,") if m else None


def classify_source(source: dict) -> InputType:
    """source is the raw ingest payload: {url?, text?, title?, media_path?, channel, received_at}."""
    if source.get("media_path"):
        return "image"
    if source.get("url"):
        return "url"
    text = (source.get("text") or "").strip()
    if URL_RE.match(text):
        return "url"
    return "text"


def source_url(source: dict) -> str | None:
    if source.get("url"):
        return source["url"]
    text = (source.get("text") or "").strip()
    if URL_RE.match(text):
        return text
    return None
