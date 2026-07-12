"""Stage persistence helpers: write enriched data + tags + categories onto an item."""
import uuid

from sqlalchemy import text

from ..models.schemas import EnrichedItem


async def apply_enriched(session, item_id: str, resolver_id: str, enriched: EnrichedItem) -> None:
    await session.execute(
        text(
            "UPDATE items SET type=:type, title=:title, description=:description, "
            "canonical_url=:canonical_url, icon_url=:icon_url, thumbnail_url=:thumbnail_url, "
            "attributes=CAST(:attributes AS jsonb), links=CAST(:links AS jsonb), "
            "resolver_id=:resolver_id, confidence=:confidence, updated_at=now() "
            "WHERE id=:id"
        ),
        {
            "type": enriched.type,
            "title": enriched.title,
            "description": enriched.description,
            "canonical_url": enriched.canonical_url,
            "icon_url": enriched.icon_url,
            "thumbnail_url": enriched.thumbnail_url,
            "attributes": _json(enriched.attributes),
            "links": _json({k: v for k, v in enriched.links.items() if v}),
            "resolver_id": resolver_id,
            "confidence": enriched.confidence,
            "id": item_id,
        },
    )


async def set_tags(session, item_id: str, tags: list[str]) -> None:
    await session.execute(text("DELETE FROM item_tags WHERE item_id=:id"), {"id": item_id})
    for name in tags:
        tag_id = (
            await session.execute(
                text(
                    "INSERT INTO tags (name) VALUES (:n) ON CONFLICT (name) DO UPDATE "
                    "SET name=EXCLUDED.name RETURNING id"
                ),
                {"n": name},
            )
        ).scalar()
        await session.execute(
            text(
                "INSERT INTO item_tags (item_id, tag_id) VALUES (:i, :t) "
                "ON CONFLICT DO NOTHING"
            ),
            {"i": item_id, "t": tag_id},
        )


async def set_categories(session, item_id: str, category_names: list[str]) -> None:
    await session.execute(text("DELETE FROM item_categories WHERE item_id=:id"), {"id": item_id})
    for name in category_names:
        cat_id = (
            await session.execute(
                text("SELECT id FROM categories WHERE name=:n ORDER BY parent_id NULLS FIRST LIMIT 1"),
                {"n": name},
            )
        ).scalar()
        if cat_id:
            await session.execute(
                text(
                    "INSERT INTO item_categories (item_id, category_id) VALUES (:i, :c) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"i": item_id, "c": cat_id},
            )


def _json(obj) -> str:
    import json

    return json.dumps(obj, default=str)
