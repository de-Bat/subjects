"""Procrastinate app + tasks (Postgres-backed queue, NO Redis — spec Section 2 lock)."""
import logging

from procrastinate import App, PsycopgConnector

from .config import get_settings

log = logging.getLogger(__name__)


def _dsn() -> str:
    # procrastinate/psycopg wants a libpq DSN, not the SQLAlchemy '+asyncpg' URL.
    return get_settings().database_dsn


app = App(connector=PsycopgConnector(conninfo=_dsn()))


@app.task(name="process_item", queue="pipeline", pass_context=False)
async def process_item(item_id: str) -> None:
    """Enrichment runs as an async job. The whole staged chain lives in pipeline.run."""
    from .pipeline.run import run_pipeline

    await run_pipeline(item_id)
