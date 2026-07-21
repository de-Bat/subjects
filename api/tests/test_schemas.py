from app.models.schemas import MoviePick, Provenance, ProvStep, VisionResult


def test_vision_result_reasoning_defaults_empty():
    assert VisionResult().reasoning == ""
    assert VisionResult(reasoning="an Instagram reel").reasoning == "an Instagram reel"


def test_moviepick_media_type_optional():
    assert MoviePick().media_type is None
    assert MoviePick(tmdb_id=1, confidence=0.9, media_type="tv").media_type == "tv"


def test_provenance_add_appends_steps_in_order():
    prov = Provenance()
    prov.add("vision", "Detected instagram")
    prov.add("resolve", "Matched by movie resolver", detail="score=0.90")
    assert [s.stage for s in prov.steps] == ["vision", "resolve"]
    assert prov.steps[1].summary == "Matched by movie resolver"
    assert prov.steps[1].detail == "score=0.90"
    assert prov.steps[0].detail is None


def test_prov_step_is_json_serialisable():
    prov = Provenance()
    prov.add("finalize", "enriched", detail="0.90 >= 0.75")
    dumped = prov.model_dump()["steps"]
    assert dumped == [{"stage": "finalize", "summary": "enriched", "detail": "0.90 >= 0.75"}]
