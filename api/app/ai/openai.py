"""OpenAI-compatible provider (used when AI_PROVIDER=openai and a key is set)."""
import base64

import httpx

from ..config import get_settings
from .provider import AIProvider

TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class OpenAIProvider(AIProvider):
    def __init__(self) -> None:
        s = get_settings()
        self.base_url = s.openai_base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {s.openai_api_key}"}

    async def _chat(self, messages: list[dict], model: str) -> str:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def vision(self, image: bytes, prompt: str, system: str | None = None) -> str:
        s = get_settings()
        b64 = base64.b64encode(image).decode()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        )
        return await self._chat(messages, s.openai_vision_model)

    async def complete(self, prompt: str, system: str | None = None) -> str:
        s = get_settings()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self._chat(messages, s.openai_text_model)

    async def embed(self, text: str) -> list[float]:
        s = get_settings()
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self.headers,
                json={
                    "model": s.openai_embed_model,
                    "input": text,
                    # Schema column is vector(768); ask OpenAI to match.
                    "dimensions": s.embed_dim,
                },
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
