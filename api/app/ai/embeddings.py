"""Text embeddings for dedup + semantic search (nomic-embed-text -> pgvector)."""
from ..config import get_settings
from .provider import get_provider


async def embed_text(text: str) -> list[float] | None:
    text = (text or "").strip()
    if not text:
        return None
    vec = await get_provider().embed(text[:4000])
    dim = get_settings().embed_dim
    if len(vec) != dim:
        # Column is vector(768); a mismatched model would corrupt search. Skip instead.
        return None
    return vec


def item_embedding_text(title: str | None, description: str | None, canonical_url: str | None) -> str:
    return "\n".join(p for p in (title, description, canonical_url) if p)
