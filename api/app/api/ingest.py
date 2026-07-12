"""POST /api/ingest — the single ingestion endpoint every channel is a thin client of.

Accepts multipart/form-data (files + optional title/text/url) OR application/json
({url?, text?, title?}). Persists a stub item (status=pending), enqueues the pipeline
job, returns 201 immediately. Never blocks on enrichment (spec Section 5).
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import notify_item_event
from ..models.schemas import IngestResponse
from .deps import get_db, require_token

router = APIRouter()

MEDIA_SUBDIR = "media"
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


async def _create_stub(session: AsyncSession, source: dict) -> uuid.UUID:
    item_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO items (id, type, status, title, source) "
            "VALUES (:id, 'generic', 'pending', :title, CAST(:source AS jsonb))"
        ),
        {
            "id": item_id,
            "title": source.get("title") or source.get("text", "")[:120] or None,
            "source": _json(source),
        },
    )
    await notify_item_event(session, "item.created", str(item_id), {"status": "pending"})
    return item_id


async def _enqueue(item_id: uuid.UUID) -> None:
    from ..jobs import app, process_item

    async with app.open_async():
        await process_item.defer_async(item_id=str(item_id))


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest(
    request: Request,
    _: None = Depends(require_token),
    session: AsyncSession = Depends(get_db),
    title: str | None = Form(default=None),
    text_field: str | None = Form(default=None, alias="text"),
    url: str | None = Form(default=None),
    media: UploadFile | None = File(default=None),
) -> IngestResponse:
    content_type = request.headers.get("content-type", "")
    channel = request.headers.get("x-subjects-channel", "unknown")

    source: dict = {
        "channel": channel,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    if content_type.startswith("application/json"):
        body = await request.json()
        source.update({k: body.get(k) for k in ("url", "text", "title") if body.get(k)})
    else:
        if title:
            source["title"] = title
        if text_field:
            source["text"] = text_field
        if url:
            source["url"] = url
        if media is not None:
            source["media_path"] = await _save_media(media)
            source["media_content_type"] = media.content_type

    item_id = await _create_stub(session, source)
    await session.commit()

    # Enqueue AFTER commit so the worker can read the stub.
    await _enqueue(item_id)

    return IngestResponse(id=item_id, status="pending")


async def _save_media(media: UploadFile) -> str:
    data_dir = Path(get_settings().data_dir) / MEDIA_SUBDIR
    data_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(media.filename or "").suffix or ".png"
    dest = data_dir / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(await media.read())
    return str(dest)


def _json(obj) -> str:
    import json

    return json.dumps(obj, default=str)
