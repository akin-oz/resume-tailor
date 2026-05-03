from __future__ import annotations

import os

import httpx
import pytest
from app.domain.tailor_ai import (
    _AIExperience,
    _user_prompt,
    validate_experiences,
    validate_profile,
)
from app.routers.tailor import _translate_openai_error
from openai import APIConnectionError, APITimeoutError, RateLimitError

# --- validate_profile -----------------------------------------------------

# A valid 60-word profile with no banned phrases or em dashes.
_VALID_PROFILE = (
    "Backend engineer with eight years building payment platforms. Led teams of "
    "three to seven, owned services from design through production rollout, "
    "and care a lot about clean APIs and observability. Comfortable in Python "
    "and PostgreSQL, recently working in FastAPI. Looking to bring this "
    "experience to a senior role on a payments-adjacent team that values craft."
)

_SEED = (
    "Backend engineer with eight years building payment platforms. Led teams "
    "and care a lot about clean APIs and observability."
)


def test_valid_profile_passes() -> None:
    profile, fallback = validate_profile(_VALID_PROFILE, _SEED)
    assert fallback is False
    assert profile == _VALID_PROFILE.strip()


def test_banned_phrase_falls_back() -> None:
    bad = _VALID_PROFILE.replace("Looking to bring", "Thrilled to bring")
    profile, fallback = validate_profile(bad, _SEED)
    assert fallback is True
    assert profile != bad


def test_em_dash_falls_back() -> None:
    bad = _VALID_PROFILE.replace("Looking to bring", "Looking — eagerly — to bring")
    _, fallback = validate_profile(bad, _SEED)
    assert fallback is True


def test_too_few_words_falls_back() -> None:
    bad = "A short profile that's way under the forty-five-word floor."
    _, fallback = validate_profile(bad, _SEED)
    assert fallback is True


def test_too_many_words_falls_back() -> None:
    bad = " ".join(["word"] * 100)
    _, fallback = validate_profile(bad, _SEED)
    assert fallback is True


def test_double_hyphen_falls_back() -> None:
    bad = _VALID_PROFILE.replace("Looking to", "Looking--mostly--to")
    _, fallback = validate_profile(bad, _SEED)
    assert fallback is True


# --- validate_experiences -------------------------------------------------


def test_unknown_story_ids_dropped() -> None:
    ai = [_AIExperience(experience_id="exp1", story_ids=["s1", "ghost", "s2", "another-ghost"])]
    pool = {"exp1": {"s1", "s2", "s3"}}
    cleaned, dropped = validate_experiences(ai, pool)
    assert len(cleaned) == 1
    assert cleaned[0].story_ids == ["s1", "s2"]
    assert dropped == ["ghost", "another-ghost"]


def test_unknown_experience_id_drops_all_its_stories() -> None:
    ai = [_AIExperience(experience_id="not-real", story_ids=["s1", "s2"])]
    pool = {"exp1": {"s1", "s2"}}
    cleaned, dropped = validate_experiences(ai, pool)
    assert cleaned == []
    assert dropped == ["s1", "s2"]


def test_all_valid_passes_through() -> None:
    ai = [
        _AIExperience(experience_id="exp1", story_ids=["s1", "s2"]),
        _AIExperience(experience_id="exp2", story_ids=["t1"]),
    ]
    pool = {"exp1": {"s1", "s2", "s3"}, "exp2": {"t1"}}
    cleaned, dropped = validate_experiences(ai, pool)
    assert dropped == []
    assert [e.experience_id for e in cleaned] == ["exp1", "exp2"]
    assert cleaned[0].story_ids == ["s1", "s2"]


def test_duplicate_valid_story_ids_are_deduplicated() -> None:
    # Repeated valid IDs are normalized; not treated as hallucinations.
    ai = [_AIExperience(experience_id="exp1", story_ids=["s1", "s1", "s2", "s1"])]
    pool = {"exp1": {"s1", "s2"}}
    cleaned, dropped = validate_experiences(ai, pool)
    assert cleaned[0].story_ids == ["s1", "s2"]
    assert dropped == []


def test_experience_with_no_valid_stories_is_skipped() -> None:
    # If every ID the model picked for an experience was invalid, drop the
    # whole experience — no point rendering a header with no bullets.
    ai = [
        _AIExperience(experience_id="exp1", story_ids=["ghost-a", "ghost-b"]),
        _AIExperience(experience_id="exp2", story_ids=["t1"]),
    ]
    pool = {"exp1": {"s1", "s2"}, "exp2": {"t1"}}
    cleaned, dropped = validate_experiences(ai, pool)
    assert [e.experience_id for e in cleaned] == ["exp2"]
    assert dropped == ["ghost-a", "ghost-b"]


# --- _user_prompt ---------------------------------------------------------


def test_user_prompt_includes_keywords_and_archetype(resume, jd_backend) -> None:  # type: ignore[no-untyped-def]
    from app.domain.models import TailorRequest, TailorSettings

    req = TailorRequest(resume=resume, jd=jd_backend, settings=TailorSettings())
    body = _user_prompt(req, "backend")
    assert '"detected_archetype": "backend"' in body
    assert "api design" in body  # keyword from the resume fixture
    assert "tiebreaker_preference" in body


# --- error translation ----------------------------------------------------


def _fake_response(status: int) -> httpx.Response:
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return httpx.Response(status, request=req)


def test_rate_limit_maps_to_503_with_retry_after() -> None:
    err = RateLimitError("rate limited", response=_fake_response(429), body=None)
    resp = _translate_openai_error(err)
    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "10"
    assert resp.media_type == "application/problem+json"


def test_timeout_maps_to_503() -> None:
    err = APITimeoutError(httpx.Request("POST", "https://api.openai.com/v1/x"))
    resp = _translate_openai_error(err)
    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "5"


def test_connection_error_maps_to_503() -> None:
    err = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/x"))
    resp = _translate_openai_error(err)
    assert resp.status_code == 503


def test_other_errors_propagate() -> None:
    with pytest.raises(ValueError):
        _translate_openai_error(ValueError("not an openai error"))


# --- integration: gated on OPENAI_API_KEY ---------------------------------


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set; skipping live AI integration test",
)
def test_live_openai_path_returns_valid_result(resume, jd_backend) -> None:  # type: ignore[no-untyped-def]
    import asyncio

    from app.domain.models import TailorRequest, TailorSettings
    from app.domain.tailor_ai import tailor_ai
    from openai import AsyncOpenAI

    async def _run() -> None:
        client = AsyncOpenAI()
        result = await tailor_ai(
            TailorRequest(resume=resume, jd=jd_backend, settings=TailorSettings()),
            client=client,
        )
        assert 45 <= len(result.profile.split()) <= 75 or result.profile_fallback_used
        # No invented IDs slipped through.
        valid_ids = {s.id for e in resume.experiences for s in e.stories}
        for te in result.experiences:
            for sid in te.story_ids:
                assert sid in valid_ids

    asyncio.run(_run())
