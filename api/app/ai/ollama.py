"""Ollama provider (default). Base URL + model names from config / runtime settings."""
import base64

import httpx

from ..config import get_settings
from ..services import runtime_settings
from .provider import AIProvider

TIMEOUT = httpx.Timeout(300.0, connect=10.0)


class OllamaProvider(AIProvider):
    def __init__(self) -> None:
        self.base_url = get_settings().ollama_base_url.rstrip("/")

    async def _chat(self, messages: list[dict], model: str) -> str:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False, "format": "json"},
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    async def vision(self, image: bytes, prompt: str, system: str | None = None) -> str:
        model = await runtime_settings.effective("vision_model", get_settings().vision_model)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": prompt,
                "images": [base64.b64encode(image).decode()],
            }
        )
        return await self._chat(messages, model)

    async def complete(self, prompt: str, system: str | None = None) -> str:
        model = await runtime_settings.effective("text_model", get_settings().text_model)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self._chat(messages, model)

    async def embed(self, text: str) -> list[float]:
        model = await runtime_settings.effective("embed_model", get_settings().embed_model)
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
