"""Worker entrypoint: `python -m app.worker`. Runs migrations + procrastinate schema + job loop."""
import asyncio
import logging

from sqlalchemy import text

from .db import get_engine, run_migrations
from .jobs import app

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("worker")


async def _procrastinate_schema_present() -> bool:
    async with get_engine().connect() as conn:
        row = (
            await conn.execute(text("SELECT to_regclass('public.procrastinate_jobs')"))
        ).scalar()
        return row is not None


async def _apply_procrastinate_schema() -> None:
    # procrastinate's schema SQL is not idempotent, so apply only when absent.
    if await _procrastinate_schema_present():
        log.info("procrastinate schema already present")
        return
    await app.schema_manager.apply_schema_async()
    log.info("procrastinate schema applied")


async def main() -> None:
    await run_migrations()  # our schema + seed taxonomy (idempotent)
    async with app.open_async():
        await _apply_procrastinate_schema()
        log.info("worker starting; polling 'pipeline' queue")
        await app.run_worker_async(queues=["pipeline"])


if __name__ == "__main__":
    asyncio.run(main())
