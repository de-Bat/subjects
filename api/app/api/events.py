"""GET /api/events — SSE stream of item.updated/created events, fed by Postgres LISTEN/NOTIFY."""
import asyncio
import logging

import psycopg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..config import get_settings
from ..db import ITEM_EVENTS_CHANNEL
from .deps import require_token_query

router = APIRouter()
log = logging.getLogger(__name__)

KEEPALIVE_SECONDS = 20


async def _event_source(request: Request):
    """Dedicated LISTEN connection; yields SSE frames. Keepalive comments prevent proxy timeouts."""
    conn = await psycopg.AsyncConnection.connect(get_settings().database_dsn, autocommit=True)
    try:
        await conn.execute(f"LISTEN {ITEM_EVENTS_CHANNEL}")
        yield ": connected\n\n"
        gen = conn.notifies()
        while True:
            if await request.is_disconnected():
                break
            try:
                notify = await asyncio.wait_for(gen.__anext__(), timeout=KEEPALIVE_SECONDS)
                yield f"event: item\ndata: {notify.payload}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.warning("SSE stream error: %s", exc)
    finally:
        await conn.close()


@router.get("/events")
async def events(request: Request, _: None = Depends(require_token_query)) -> StreamingResponse:
    return StreamingResponse(
        _event_source(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
