"""Image -> {detected_service, ocr_text, candidate_entities, visible_url} via the VLM."""
from ..models.schemas import VisionResult
from . import prompts
from .provider import get_provider, vision_json


async def extract_image_signals(image: bytes) -> VisionResult:
    """Run the Appendix B.1 prompt; on double parse failure fall back to an empty generic result."""
    result = await vision_json(
        get_provider(), VisionResult, image, prompts.VISION_USER, system=prompts.VISION_SYSTEM
    )
    return result or VisionResult()
