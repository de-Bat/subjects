"""Runtime-editable settings stored in app_settings, overriding env config.

Lets the Settings page change models/thresholds without a redeploy (Phase 5).
Fail-soft: any DB error falls back to the env default so the pipeline never
dies because of a settings lookup.
"""
from sqlalchemy import text

from ..db import get_session_factory

# Keys the Settings page may override.
ALLOWED_KEYS = {
    "vision_model",
    "text_model",
    "embed_model",
    "confidence_auto",
    "dedup_threshold",
}


async def get_override(key: str) -> str | None:
    if key not in ALLOWED_KEYS:
        return None
    try:
        async with get_session_factory()() as session:
            row = (
                await session.execute(
                    text("SELECT value FROM app_settings WHERE key = :k"), {"k": key}
                )
            ).first()
            return row[0] if row else None
    except Exception:
        return None


async def effective(key: str, default: str) -> str:
    return await get_override(key) or default


async def effective_float(key: str, default: float) -> float:
    raw = await get_override(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


async def set_override(key: str, value: str | None) -> None:
    if key not in ALLOWED_KEYS:
        raise ValueError(f"setting not editable: {key}")
    async with get_session_factory()() as session:
        if value is None or value == "":
            await session.execute(text("DELETE FROM app_settings WHERE key = :k"), {"k": key})
        else:
            await session.execute(
                text(
                    "INSERT INTO app_settings (key, value) VALUES (:k, :v) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
                ),
                {"k": key, "v": value},
            )
        await session.commit()


async def all_overrides() -> dict[str, str]:
    try:
        async with get_session_factory()() as session:
            rows = (await session.execute(text("SELECT key, value FROM app_settings"))).all()
            return {k: v for k, v in rows}
    except Exception:
        return {}
