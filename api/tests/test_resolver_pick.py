from app.models.schemas import CandidateEntity, Signals, VisionResult
from app.resolvers import registry
from app.resolvers.social import SocialResolver


def test_instagram_host_detected_as_social():
    sig = Signals(input_type="url", canonical_url="https://www.instagram.com/reel/abc/")
    assert SocialResolver().detect(sig) >= 0.85


def test_media_promo_beats_social():
    vision = VisionResult(
        detected_service="instagram",
        candidate_entities=[
            CandidateEntity(type="media_title", value="Priscilla"),
            CandidateEntity(type="person", value="Annette Bening"),
            CandidateEntity(type="provider", value="Apple TV+"),
        ],
    )
    sig = Signals(input_type="image", canonical_url="https://www.instagram.com/reel/abc/", vision=vision)
    assert registry.pick(sig).id == "movie"


def test_plain_social_post_stays_social():
    vision = VisionResult(detected_service="instagram", ocr_text="just a selfie")
    sig = Signals(input_type="image", canonical_url="https://www.instagram.com/p/xyz/", vision=vision)
    assert registry.pick(sig).id == "social"
