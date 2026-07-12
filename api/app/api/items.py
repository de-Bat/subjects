"""Items CRUD + review actions + media serving."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import get_settings
from ..db import notify_item_event
from ..models.orm import Item
from ..models.schemas import ItemOut, ItemPatch
from .deps import get_db, require_token

router = APIRouter()


async def _load(session: AsyncSession, item_id: uuid.UUID) -> Item:
    from sqlalchemy import select

    item = (
        await session.execute(
            select(Item)
            .where(Item.id == item_id)
            .options(selectinload(Item.tags), selectinload(Item.categories))
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "item not found")
    return item


@router.get("/items", response_model=list[ItemOut])
async def list_items(
    session: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    type_filter: str | None = Query(default=None, alias="type"),
    category: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Item]:
    from sqlalchemy import select

    stmt = select(Item).options(selectinload(Item.tags), selectinload(Item.categories))
    if status_filter:
        stmt = stmt.where(Item.status == status_filter)
    else:
        stmt = stmt.where(Item.status != "duplicate")
    if type_filter:
        stmt = stmt.where(Item.type == type_filter)
    if category:
        stmt = stmt.where(
            text(
                "items.id IN (SELECT ic.item_id FROM item_categories ic "
                "JOIN categories c ON c.id=ic.category_id WHERE c.name=:cat)"
            ).bindparams(cat=category)
        )
    if tag:
        stmt = stmt.where(
            text(
                "items.id IN (SELECT it.item_id FROM item_tags it "
                "JOIN tags t ON t.id=it.tag_id WHERE t.name=:tag)"
            ).bindparams(tag=tag)
        )
    stmt = stmt.order_by(Item.created_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/items/{item_id}", response_model=ItemOut)
async def get_item(item_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> Item:
    return await _load(session, item_id)


@router.patch("/items/{item_id}", response_model=ItemOut, dependencies=[Depends(require_token)])
async def patch_item(
    item_id: uuid.UUID, patch: ItemPatch, session: AsyncSession = Depends(get_db)
) -> Item:
    item = await _load(session, item_id)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await session.flush()
    await notify_item_event(session, "item.updated", str(item_id), {"stage": "manual"})
    await session.commit()
    await _reindex(item_id)
    return await _load(session, item_id)


@router.post(
    "/items/{item_id}/approve", response_model=ItemOut, dependencies=[Depends(require_token)]
)
async def approve_item(item_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> Item:
    """Review action: accept a needs_review item as enriched."""
    await session.execute(
        text("UPDATE items SET status='enriched', updated_at=now() WHERE id=:id"), {"id": item_id}
    )
    await notify_item_event(session, "item.updated", str(item_id), {"status": "enriched"})
    await session.commit()
    await _reindex(item_id)
    return await _load(session, item_id)


@router.post(
    "/items/{item_id}/reject", response_model=ItemOut, dependencies=[Depends(require_token)]
)
async def reject_item(item_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> Item:
    await session.execute(
        text("UPDATE items SET status='rejected', updated_at=now() WHERE id=:id"), {"id": item_id}
    )
    await notify_item_event(session, "item.updated", str(item_id), {"status": "rejected"})
    await session.commit()
    return await _load(session, item_id)


@router.delete("/items/{item_id}", status_code=204, dependencies=[Depends(require_token)])
async def delete_item(item_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> None:
    await session.execute(text("DELETE FROM items WHERE id=:id"), {"id": item_id})
    await session.commit()
    from ..services.search import delete_item as search_delete

    await search_delete(str(item_id))


@router.post("/items/{item_id}/reprocess", dependencies=[Depends(require_token)])
async def reprocess_item(item_id: uuid.UUID, session: AsyncSession = Depends(get_db)) -> dict:
    await _load(session, item_id)  # 404 if missing
    from ..jobs import app, process_item

    async with app.open_async():
        await process_item.defer_async(item_id=str(item_id))
    return {"status": "queued"}


@router.get("/media/{name}")
async def get_media(name: str) -> FileResponse:
    """Serve uploaded screenshots (public read; the LAN guard is on writes)."""
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "bad name")
    path = Path(get_settings().data_dir) / "media" / name
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path)


async def _reindex(item_id: uuid.UUID) -> None:
    try:
        from ..services.search import index_item

        await index_item(str(item_id))
    except Exception:
        pass
