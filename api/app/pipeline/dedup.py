"""Stage 6 — embed the item and cosine-search pgvector for near-duplicates.

Same repo shared as screenshot AND link should collapse to one item.
On a match above threshold we link (record duplicate_of) rather than duplicate.
"""
import logging

from sqlalchemy import text

from ..ai.embeddings import embed_text, item_embedding_text
from ..config import get_settings
from ..services import runtime_settings

log = logging.getLogger(__name__)


async def embed_and_find_duplicate(session, item_id: str, title, description, canonical_url) -> str | None:
    """Compute + store embedding; return the id of an existing near-duplicate item, if any."""
    # Strong signal first: identical canonical URL is a definite duplicate.
    if canonical_url:
        row = (
            await session.execute(
                text(
                    "SELECT id FROM items WHERE canonical_url = :u AND id <> :id "
                    "AND status <> 'failed' ORDER BY created_at LIMIT 1"
                ),
                {"u": canonical_url, "id": item_id},
            )
        ).first()
        if row:
            return str(row[0])

    embed_input = item_embedding_text(title, description, canonical_url)
    try:
        vec = await embed_text(embed_input)
    except Exception as exc:
        log.warning("embedding failed: %s", exc)
        vec = None
    if vec is None:
        return None

    vec_literal = "[" + ",".join(str(x) for x in vec) + "]"
    await session.execute(
        text("UPDATE items SET embedding = :v WHERE id = :id"),
        {"v": vec_literal, "id": item_id},
    )

    threshold = await runtime_settings.effective_float(
        "dedup_threshold", get_settings().dedup_threshold
    )
    # pgvector cosine distance (<=>) : similarity = 1 - distance.
    row = (
        await session.execute(
            text(
                "SELECT id, 1 - (embedding <=> :v) AS sim FROM items "
                "WHERE id <> :id AND embedding IS NOT NULL AND status <> 'failed' "
                "ORDER BY embedding <=> :v LIMIT 1"
            ),
            {"v": vec_literal, "id": item_id},
        )
    ).first()
    if row and row[1] is not None and float(row[1]) >= threshold:
        return str(row[0])
    return None
