"""Meilisearch integration (Phase 4). Full-text index of items; degrades gracefully if down."""
import logging

import httpx
from sqlalchemy import text

from ..config import get_settings
from ..db import get_session_factory

log = logging.getLogger(__name__)
INDEX = "items"


def _client() -> httpx.AsyncClient:
    s = get_settings()
    headers = {}
    if s.meili_master_key:
        headers["Authorization"] = f"Bearer {s.meili_master_key}"
    return httpx.AsyncClient(base_url=s.meili_url.rstrip("/"), headers=headers, timeout=15.0)


async def ensure_index() -> None:
    async with _client() as client:
        await client.post("/indexes", json={"uid": INDEX, "primaryKey": "id"})
        await client.patch(
            f"/indexes/{INDEX}/settings",
            json={
                "searchableAttributes": ["title", "description", "tags", "type", "canonical_url"],
                "filterableAttributes": ["type", "status", "categories", "tags"],
                "sortableAttributes": ["created_at"],
            },
        )


async def index_item(item_id: str) -> None:
    factory = get_session_factory()
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT i.id, i.type, i.status, i.title, i.description, i.canonical_url, "
                    "i.thumbnail_url, i.icon_url, extract(epoch from i.created_at) AS created_at, "
                    "COALESCE(array_agg(DISTINCT t.name) FILTER (WHERE t.name IS NOT NULL), '{}') AS tags, "
                    "COALESCE(array_agg(DISTINCT c.name) FILTER (WHERE c.name IS NOT NULL), '{}') AS cats "
                    "FROM items i "
                    "LEFT JOIN item_tags it ON it.item_id=i.id LEFT JOIN tags t ON t.id=it.tag_id "
                    "LEFT JOIN item_categories ic ON ic.item_id=i.id LEFT JOIN categories c ON c.id=ic.category_id "
                    "WHERE i.id=:id GROUP BY i.id"
                ),
                {"id": item_id},
            )
        ).mappings().first()
    if not row:
        return
    doc = {
        "id": str(row["id"]),
        "type": row["type"],
        "status": row["status"],
        "title": row["title"],
        "description": row["description"],
        "canonical_url": row["canonical_url"],
        "thumbnail_url": row["thumbnail_url"],
        "icon_url": row["icon_url"],
        "created_at": row["created_at"],
        "tags": list(row["tags"]),
        "categories": list(row["cats"]),
    }
    async with _client() as client:
        await client.post(f"/indexes/{INDEX}/documents", json=[doc])


async def delete_item(item_id: str) -> None:
    try:
        async with _client() as client:
            await client.delete(f"/indexes/{INDEX}/documents/{item_id}")
    except Exception as exc:
        log.warning("search delete failed: %s", exc)


async def search(query: str, limit: int = 30, filters: str | None = None) -> list[dict]:
    async with _client() as client:
        body = {"q": query, "limit": limit}
        if filters:
            body["filter"] = filters
        resp = await client.post(f"/indexes/{INDEX}/search", json=body)
        resp.raise_for_status()
        return resp.json().get("hits", [])
