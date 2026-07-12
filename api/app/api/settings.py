"""GET/PUT /api/settings — runtime config (models, thresholds) editable without redeploy.

Keys, presence-of-secrets (never the secret values), and current effective models.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..config import get_settings
from ..services import runtime_settings
from .deps import require_token

router = APIRouter()


class SettingsOut(BaseModel):
    ai_provider: str
    effective: dict
    overrides: dict
    defaults: dict
    keys_present: dict
    editable_keys: list[str]


class SettingsPatch(BaseModel):
    vision_model: str | None = None
    text_model: str | None = None
    embed_model: str | None = None
    confidence_auto: str | None = None
    dedup_threshold: str | None = None


@router.get("/settings", response_model=SettingsOut, dependencies=[Depends(require_token)])
async def read_settings() -> SettingsOut:
    s = get_settings()
    overrides = await runtime_settings.all_overrides()
    defaults = {
        "vision_model": s.vision_model,
        "text_model": s.text_model,
        "embed_model": s.embed_model,
        "confidence_auto": str(s.confidence_auto),
        "dedup_threshold": str(s.dedup_threshold),
    }
    effective = {k: overrides.get(k, v) for k, v in defaults.items()}
    return SettingsOut(
        ai_provider=s.ai_provider,
        effective=effective,
        overrides=overrides,
        defaults=defaults,
        keys_present={
            "github_token": bool(s.github_token),
            "tmdb_api_key": bool(s.tmdb_api_key),
            "openai_api_key": bool(s.openai_api_key),
        },
        editable_keys=sorted(runtime_settings.ALLOWED_KEYS),
    )


@router.put("/settings", dependencies=[Depends(require_token)])
async def update_settings(patch: SettingsPatch) -> dict:
    for key, value in patch.model_dump(exclude_unset=True).items():
        await runtime_settings.set_override(key, value)
    return {"status": "ok"}
