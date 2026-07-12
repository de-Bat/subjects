"""Env-driven settings (Pydantic Settings). All model names come from config, never hard-coded."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    app_token: str = "dev-token"
    database_url: str = "postgresql+asyncpg://subjects:subjects@localhost:5432/subjects"
    database_dsn: str = "postgresql://subjects:subjects@localhost:5432/subjects"
    data_dir: str = "/data"
    public_base_url: str = "http://localhost:8000"

    # AI provider
    ai_provider: str = "ollama"  # ollama | openai | nim
    ollama_base_url: str = "http://localhost:11434"
    vision_model: str = "qwen2.5vl:7b"
    text_model: str = "qwen2.5vl:7b"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_vision_model: str = "gpt-4o-mini"
    openai_text_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    # NVIDIA NIM (self-hosted or build.nvidia.com — OpenAI-compatible protocol)
    nim_api_key: str = ""
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_vision_model: str = "meta/llama-3.2-90b-vision-instruct"
    nim_text_model: str = "meta/llama-3.1-70b-instruct"
    nim_embed_model: str = "nvidia/nv-embedqa-e5-v5"

    # External APIs (single set of keys — single-user deliberate, Section 8)
    github_token: str = ""
    tmdb_api_key: str = ""

    # Pipeline
    confidence_auto: float = 0.8
    dedup_threshold: float = 0.90

    # Search
    meili_url: str = "http://localhost:7700"
    meili_master_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
