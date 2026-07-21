"""Pipeline orchestrator: runs the staged chain for one item, emitting SSE after each stage.

classify -> extract -> resolve -> enrich -> categorize -> dedup -> finalize.
Every stage updates the item and emits item.updated so the UI reflects progress live.
"""
import logging

from sqlalchemy import text

from ..config import get_settings
from ..db import get_session_factory, notify_item_event
from ..services import runtime_settings
from . import categorize as categorize_stage
from . import dedup as dedup_stage
from . import enrich as persist
from .extract import extract
from .resolve import resolve_and_enrich

log = logging.getLogger(__name__)


async def _emit(session, item_id: str, stage: str, status: str | None = None) -> None:
    await notify_item_event(session, "item.updated", item_id, {"stage": stage, "status": status})


async def run_pipeline(item_id: str) -> None:
    factory = get_session_factory()

    # Load the raw payload.
    async with factory() as session:
        row = (
            await session.execute(text("SELECT source FROM items WHERE id=:id"), {"id": item_id})
        ).first()
        if not row:
            log.warning("item %s vanished before pipeline", item_id)
            return
        source = row[0] or {}

    try:
        # 1-2. classify + extract
        signals = await extract(source)
        async with factory() as session:
            await _emit(session, item_id, "extract")
            await session.commit()

        # 3-4. resolve + enrich
        resolver_id, enriched = await resolve_and_enrich(signals)
        async with factory() as session:
            await persist.apply_enriched(session, item_id, resolver_id, enriched)
            await _emit(session, item_id, "enrich", "enriched")
            await session.commit()

        # 5. categorize
        async with factory() as session:
            cat = await categorize_stage.categorize(session, enriched)
            await persist.set_categories(session, item_id, cat.categories)
            await persist.set_tags(session, item_id, cat.tags)
            await _emit(session, item_id, "categorize")
            await session.commit()

        # 6. dedup
        duplicate_of = None
        async with factory() as session:
            duplicate_of = await dedup_stage.embed_and_find_duplicate(
                session, item_id, enriched.title, enriched.description, enriched.canonical_url
            )
            if duplicate_of:
                await session.execute(
                    text(
                        "UPDATE items SET status='duplicate', "
                        "attributes = attributes || jsonb_build_object('duplicate_of', CAST(:dup AS text)), "
                        "updated_at=now() WHERE id=:id"
                    ),
                    {"dup": duplicate_of, "id": item_id},
                )
                await _emit(session, item_id, "dedup", "duplicate")
                await session.commit()

        if duplicate_of:
            await _index_search(item_id)
            return

        # 7. finalize — confidence gate
        threshold = await runtime_settings.effective_float(
            "confidence_auto", get_settings().confidence_auto
        )
        final_status = "enriched" if (enriched.confidence or 0) >= threshold else "needs_review"
        async with factory() as session:
            await session.execute(
                text("UPDATE items SET status=:s, updated_at=now() WHERE id=:id"),
                {"s": final_status, "id": item_id},
            )
            await _emit(session, item_id, "finalize", final_status)
            await session.commit()

        await _index_search(item_id)

    except Exception as exc:
        log.exception("pipeline failed for %s", item_id)
        async with factory() as session:
            await session.execute(
                text(
                    "UPDATE items SET status='failed', "
                    "attributes = attributes || jsonb_build_object('error', CAST(:e AS text)), updated_at=now() "
                    "WHERE id=:id"
                ),
                {"e": str(exc)[:500], "id": item_id},
            )
            await _emit(session, item_id, "error", "failed")
            await session.commit()


async def _index_search(item_id: str) -> None:
    """Best-effort Meilisearch index (Phase 4). Never fails the pipeline."""
    try:
        from ..services.search import index_item

        await index_item(item_id)
    except Exception as exc:
        log.warning("search index failed for %s: %s", item_id, exc)
