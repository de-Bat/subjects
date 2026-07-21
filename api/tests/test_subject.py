from app.models.schemas import CandidateEntity, PrimarySubject, VisionResult
from app.pipeline.subject import subject_entities


def test_primary_subject_defaults():
    ps = PrimarySubject()
    assert ps.subject_type == "generic" and ps.title is None


def test_entity_role_defaults_to_subject():
    assert CandidateEntity(type="movie", value="Dune").role == "subject"


def test_subject_entities_filters_collateral():
    vision = VisionResult(candidate_entities=[
        CandidateEntity(type="media_title", value="Priscilla", role="subject"),
        CandidateEntity(type="brand", value="SomeAd", role="collateral"),
    ])
    kept = subject_entities(vision)
    assert [e.value for e in kept] == ["Priscilla"]


def test_subject_entities_none_vision():
    assert subject_entities(None) == []
