"""Category tree CRUD (taxonomy editable by the user; Settings page uses these)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.orm import Category
from ..models.schemas import CategoryCreate, CategoryOut, CategoryPatch
from .deps import get_db, require_token

router = APIRouter()


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(session: AsyncSession = Depends(get_db)) -> list[Category]:
    return list((await session.execute(select(Category).order_by(Category.name))).scalars().all())


@router.get("/categories/tree")
async def category_tree(session: AsyncSession = Depends(get_db)) -> list[dict]:
    """Nested tree + per-category item counts for the browse UI."""
    cats = list((await session.execute(select(Category))).scalars().all())
    counts = {
        r[0]: r[1]
        for r in (
            await session.execute(
                text(
                    "SELECT category_id, count(*) FROM item_categories ic "
                    "JOIN items i ON i.id=ic.item_id WHERE i.status <> 'duplicate' "
                    "GROUP BY category_id"
                )
            )
        ).all()
    }
    nodes = {
        c.id: {"id": str(c.id), "name": c.name, "parent_id": str(c.parent_id) if c.parent_id else None,
               "count": counts.get(c.id, 0), "children": []}
        for c in cats
    }
    roots = []
    for c in cats:
        if c.parent_id and c.parent_id in nodes:
            nodes[c.parent_id]["children"].append(nodes[c.id])
        else:
            roots.append(nodes[c.id])
    return roots


@router.post("/categories", response_model=CategoryOut, dependencies=[Depends(require_token)])
async def create_category(
    payload: CategoryCreate, session: AsyncSession = Depends(get_db)
) -> Category:
    cat = Category(name=payload.name, parent_id=payload.parent_id)
    session.add(cat)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(409, "category already exists")
    await session.refresh(cat)
    return cat


@router.patch(
    "/categories/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_token)]
)
async def patch_category(
    category_id: uuid.UUID, payload: CategoryPatch, session: AsyncSession = Depends(get_db)
) -> Category:
    cat = await session.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    await session.commit()
    await session.refresh(cat)
    return cat


@router.delete("/categories/{category_id}", status_code=204, dependencies=[Depends(require_token)])
async def delete_category(
    category_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> None:
    cat = await session.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "not found")
    await session.delete(cat)
    await session.commit()
