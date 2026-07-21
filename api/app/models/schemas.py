"""Pydantic v2 schemas: API I/O + pipeline data contracts."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InputType = Literal["image", "url", "text"]


# ---------- API ----------

class IngestJSON(BaseModel):
    url: str | None = None
    text: str | None = None
    title: str | None = None


class IngestResponse(BaseModel):
    id: uuid.UUID
    status: str


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    status: str
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    icon_url: str | None = None
    thumbnail_url: str | None = None
    attributes: dict = {}
    links: dict = {}
    source: dict = {}
    resolver_id: str | None = None
    confidence: float | None = None
    created_at: datetime
    updated_at: datetime
    tags: list[TagOut] = []
    categories: list[CategoryOut] = []


class ItemPatch(BaseModel):
    type: str | None = None
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    status: str | None = None


class CategoryCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None


class CategoryPatch(BaseModel):
    name: str | None = None
    parent_id: uuid.UUID | None = None


# ---------- Pipeline contracts ----------

class CandidateEntity(BaseModel):
    type: str
    value: str


class VisionResult(BaseModel):
    """Strict-JSON output of the VLM extraction prompt (Appendix B.1)."""
    detected_service: str = "generic"
    visible_url: str | None = None
    title_guess: str | None = None
    ocr_text: str = ""
    reasoning: str = ""
    candidate_entities: list[CandidateEntity] = Field(default_factory=list)


class Signals(BaseModel):
    """Everything the extract stage learned; the input to every resolver's detect/enrich."""
    input_type: InputType
    url: str | None = None
    text: str | None = None
    title: str | None = None
    image_path: str | None = None
    # URL-path extraction
    canonical_url: str | None = None
    og: dict = Field(default_factory=dict)          # flattened Open Graph / Twitter Card props
    jsonld: list = Field(default_factory=list)       # schema.org JSON-LD blocks
    oembed: dict = Field(default_factory=dict)
    body_text: str | None = None                     # readability/trafilatura extract
    # Image-path extraction
    vision: VisionResult | None = None


class EnrichedItem(BaseModel):
    """What a resolver's enrich() returns; persisted onto the item."""
    type: str = "generic"
    title: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    icon_url: str | None = None
    thumbnail_url: str | None = None
    attributes: dict = Field(default_factory=dict)
    links: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    category_hints: list[str] = Field(default_factory=list)
    confidence: float = 0.0


# ---------- LLM structured outputs (Appendix B) ----------

class RepoGuess(BaseModel):
    owner: str | None = None
    repo: str | None = None
    confidence: float = 0.0


class MoviePick(BaseModel):
    tmdb_id: int | None = None
    confidence: float = 0.0
    media_type: Literal["movie", "tv"] | None = None


class CategorizeResult(BaseModel):
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ProvStep(BaseModel):
    """One user-facing step in the 'how I got there' trace."""
    stage: str
    summary: str
    detail: str | None = None


class Provenance(BaseModel):
    """Accumulates ProvSteps across a pipeline run; persisted to attributes._provenance."""
    steps: list[ProvStep] = Field(default_factory=list)

    def add(self, stage: str, summary: str, detail: str | None = None) -> None:
        self.steps.append(ProvStep(stage=stage, summary=summary, detail=detail))
