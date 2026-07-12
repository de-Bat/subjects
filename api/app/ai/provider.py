"""AI provider abstraction (spec Section 7).

Three capabilities: vision(image, prompt) -> str, complete(prompt) -> str,
embed(text) -> list[float]. Implementations: ollama (default), openai.
All model names come from config, never hard-coded.
"""
import json
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ..config import get_settings

T = TypeVar("T", bound=BaseModel)

RETRY_SUFFIX = "\nYour last reply was not valid JSON. Return only JSON."


class AIProvider(ABC):
    @abstractmethod
    async def vision(self, image: bytes, prompt: str, system: str | None = None) -> str: ...

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None) -> str: ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...


def strip_json(raw: str) -> str:
    """Strip code fences / surrounding prose down to the JSON object."""
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    # If prose surrounds the JSON, cut to first { .. last }
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start : end + 1]
    return raw


def parse_json_as(schema: type[T], raw: str) -> T | None:
    try:
        return schema.model_validate(json.loads(strip_json(raw)))
    except (json.JSONDecodeError, ValidationError):
        return None


async def complete_json(
    provider: AIProvider, schema: type[T], prompt: str, system: str | None = None
) -> T | None:
    """Ask for JSON, parse defensively, retry ONCE on parse failure (Appendix B), else None."""
    raw = await provider.complete(prompt, system=system)
    parsed = parse_json_as(schema, raw)
    if parsed is not None:
        return parsed
    raw = await provider.complete(prompt + RETRY_SUFFIX, system=system)
    return parse_json_as(schema, raw)


async def vision_json(
    provider: AIProvider, schema: type[T], image: bytes, prompt: str, system: str | None = None
) -> T | None:
    raw = await provider.vision(image, prompt, system=system)
    parsed = parse_json_as(schema, raw)
    if parsed is not None:
        return parsed
    raw = await provider.vision(image, prompt + RETRY_SUFFIX, system=system)
    return parse_json_as(schema, raw)


_provider: AIProvider | None = None


def get_provider() -> AIProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.ai_provider == "openai" and settings.openai_api_key:
            from .openai import OpenAIProvider

            _provider = OpenAIProvider()
        else:
            from .ollama import OllamaProvider

            _provider = OllamaProvider()
    return _provider
