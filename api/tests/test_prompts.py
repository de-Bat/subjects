from app.ai import prompts


def test_vision_prompt_requires_primary_subject_and_roles():
    p = prompts.VISION_SYSTEM
    assert "primary_subject" in p
    assert '"role"' in p or "role" in p
    assert "collateral" in p


def test_text_prompt_requires_primary_subject():
    assert "primary_subject" in prompts.TEXT_SIGNALS_SYSTEM
