"""GET /api/search — Meilisearch full-text (Phase 4) + pgvector semantic (Phase 5)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..ai.embeddings import embed_text
from .deps import get_db

router = APIRouter()


@router.get("/search")
async def search_items(
    q: str = Query(min_length=1),
    mode: str = Query(default="fulltext"),  # fulltext | semantic
    limit: int = Query(default=30, le=100),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if mode == "semantic":
        return {"mode": "semantic", "hits": await _semantic(session, q, limit)}
    from ..services.search import search

    try:
        hits = await search(q, limit=limit)
        return {"mode": "fulltext", "hits": hits}
    except Exception:
        # Meilisearch down -> fall back to a SQL ILIKE so search still returns something.
        return {"mode": "fulltext-fallback", "hits": await _sql_fallback(session, q, limit)}


async def _semantic(session: AsyncSession, q: str, limit: int) -> list[dict]:
    vec = await embed_text(q)
    if vec is None:
        return await _sql_fallback(session, q, limit)
    vec_literal = "[" + ",".join(str(x) for x in vec) + "]"
    rows = (
        await session.execute(
            text(
                "SELECT id, type, title, description, thumbnail_url, canonical_url, "
                "1 - (embedding <=> :v) AS score FROM items "
                "WHERE embedding IS NOT NULL AND status <> 'duplicate' "
                "ORDER BY embedding <=> :v LIMIT :lim"
            ),
            {"v": vec_literal, "lim": limit},
        )
    ).mappings().all()
    return [dict(r) | {"id": str(r["id"])} for r in rows]


async def _sql_fallback(session: AsyncSession, q: str, limit: int) -> list[dict]:
    rows = (
        await session.execute(
            text(
                "SELECT id, type, title, description, thumbnail_url, canonical_url FROM items "
                "WHERE status <> 'duplicate' AND (title ILIKE :p OR description ILIKE :p) "
                "ORDER BY created_at DESC LIMIT :lim"
            ),
            {"p": f"%{q}%", "lim": limit},
        )
    ).mappings().all()
    return [dict(r) | {"id": str(r["id"])} for r in rows]
