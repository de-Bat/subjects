"""Async SQLAlchemy engine/session + idempotent schema migration + LISTEN/NOTIFY helpers."""
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

-- Items are the core entity.
-- multi-user seam: add owner_id uuid later; v1 leaves it out (spec Section 8).
CREATE TABLE IF NOT EXISTS items (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type           text NOT NULL,
  status         text NOT NULL DEFAULT 'pending',
  title          text,
  description    text,
  canonical_url  text,
  icon_url       text,
  thumbnail_url  text,
  attributes     jsonb NOT NULL DEFAULT '{}',
  links          jsonb NOT NULL DEFAULT '{}',
  source         jsonb NOT NULL DEFAULT '{}',
  resolver_id    text,
  confidence     real,
  embedding      vector(768),
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tags (
  id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS item_tags (
  item_id uuid REFERENCES items(id) ON DELETE CASCADE,
  tag_id  uuid REFERENCES tags(id)  ON DELETE CASCADE,
  PRIMARY KEY (item_id, tag_id)
);

-- Categories form a tree; items can sit in MANY categories (multi-placement).
-- multi-user seam: add owner_id later.
CREATE TABLE IF NOT EXISTS categories (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name      text NOT NULL,
  parent_id uuid REFERENCES categories(id) ON DELETE SET NULL,
  UNIQUE NULLS NOT DISTINCT (name, parent_id)
);
CREATE TABLE IF NOT EXISTS item_categories (
  item_id     uuid REFERENCES items(id)      ON DELETE CASCADE,
  category_id uuid REFERENCES categories(id) ON DELETE CASCADE,
  PRIMARY KEY (item_id, category_id)
);

-- Runtime-editable settings (model names, thresholds) so Phase 5 needs no redeploy.
CREATE TABLE IF NOT EXISTS app_settings (
  key   text PRIMARY KEY,
  value text NOT NULL
);

CREATE INDEX IF NOT EXISTS items_status_idx ON items (status);
CREATE INDEX IF NOT EXISTS items_created_idx ON items (created_at DESC);
CREATE INDEX IF NOT EXISTS items_canonical_idx ON items (canonical_url);
"""

SEED_CATEGORIES = [
    "Development", "Links", "Movies", "Articles", "Products",
    "Recipes", "Papers", "Social", "Inbox",
]


async def run_migrations() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        # api + worker both run migrations on startup; serialize so concurrent
        # DDL (e.g. CREATE EXTENSION) can't race each other.
        await conn.execute(text("SELECT pg_advisory_xact_lock(727271)"))
        schema_no_comments = "\n".join(
            line for line in SCHEMA_SQL.splitlines() if not line.strip().startswith("--")
        )
        for stmt in [s.strip() for s in schema_no_comments.split(";") if s.strip()]:
            await conn.execute(text(stmt))
        # Seed taxonomy (editable by user afterwards)
        for name in SEED_CATEGORIES:
            await conn.execute(
                text(
                    "INSERT INTO categories (name, parent_id) VALUES (:n, NULL) "
                    "ON CONFLICT (name, parent_id) DO NOTHING"
                ),
                {"n": name},
            )


ITEM_EVENTS_CHANNEL = "item_events"


async def notify_item_event(session: AsyncSession, event: str, item_id: str, payload: dict | None = None) -> None:
    """Emit a pg_notify on the item events channel; the SSE endpoint relays it to the UI."""
    body = json.dumps({"event": event, "item_id": str(item_id), **(payload or {})})
    await session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": ITEM_EVENTS_CHANNEL, "payload": body},
    )
