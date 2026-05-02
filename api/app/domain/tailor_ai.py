"""OpenAI-mode tailor with server-side validation of the model's output.

The model receives bullet IDs and must return the same IDs. Any ID it
returns that wasn't in the input pool is dropped (logged, surfaced via
``TailorResult.dropped_story_ids``) — the model cannot smuggle in
invented bullets. The profile paragraph is checked against banned
phrases, em-dash usage, and a 45-75 word window; violations fall back
to a clean truncation of the user's ``profile_seed`` and surface via
``profile_fallback_used=True``.

When ``OPENAI_API_KEY`` isn't set, the route uses ``tailor_stub``
instead — this module is never imported on that path.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict

from .archetype import detect_archetype
from .models import (
    Archetype,
    StoryId,
    TailoredExperience,
    TailorRequest,
    TailorResult,
)
from .tailor import _truncate_profile

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "tailor_system.md"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TIMEOUT = 30.0

# Lowercase, matched as substrings in the candidate profile.
_BANNED_PHRASES: tuple[str, ...] = (
    "thrilled",
    "passionate",
    "cutting-edge",
    "cutting edge",
    "leverage",
    "synergy",
    "dynamic",
    "results-driven",
    "results driven",
    "bring to the table",
)

_PROFILE_MIN_WORDS = 45
_PROFILE_MAX_WORDS = 75


# --- Strict shapes the model must produce --------------------------------


class _AIExperience(BaseModel):
    """Per-experience selection from the model. IDs validated downstream."""

    model_config = ConfigDict(extra="forbid")
    experience_id: str
    story_ids: list[str]


class _AIResponse(BaseModel):
    """Top-level shape the model returns. Enforced by OpenAI structured output."""

    model_config = ConfigDict(extra="forbid")
    profile: str
    experiences: list[_AIExperience]
    skills: list[str]
    keywords_injected: list[str]


# --- Validators (pure) ----------------------------------------------------


def validate_profile(candidate: str, seed: str) -> tuple[str, bool]:
    """Validate a model-produced profile; fall back to the seed if it fails.

    Returns ``(profile, fallback_used)``. The fallback is a clean
    truncation of ``seed`` — guaranteed to be in the user's voice and
    free of invented facts.
    """
    text = candidate.strip()
    lower = text.lower()
    if any(phrase in lower for phrase in _BANNED_PHRASES):
        return _truncate_profile(seed), True
    if "—" in text or "--" in text:
        return _truncate_profile(seed), True
    word_count = len(text.split())
    if word_count < _PROFILE_MIN_WORDS or word_count > _PROFILE_MAX_WORDS:
        return _truncate_profile(seed), True
    return text, False


def validate_experiences(
    ai_experiences: list[_AIExperience],
    pool_by_exp_id: dict[str, set[str]],
) -> tuple[list[TailoredExperience], list[StoryId]]:
    """Drop unknown experience IDs and unknown story IDs.

    Returns ``(cleaned, dropped)``. A bogus ``experience_id`` is treated
    as a hallucination of the whole entry — every story ID it returned
    is recorded as dropped. Within a valid experience, only unknown
    story IDs are dropped; valid ones survive in the order returned.
    """
    cleaned: list[TailoredExperience] = []
    dropped: list[StoryId] = []
    for ae in ai_experiences:
        valid_pool = pool_by_exp_id.get(ae.experience_id)
        if valid_pool is None:
            dropped.extend(ae.story_ids)
            continue
        kept: list[StoryId] = []
        for sid in ae.story_ids:
            if sid in valid_pool:
                kept.append(sid)
            else:
                dropped.append(sid)
        cleaned.append(TailoredExperience(experience_id=ae.experience_id, story_ids=kept))
    return cleaned, dropped


# --- Prompt assembly + OpenAI call ----------------------------------------


def _user_prompt(req: TailorRequest, archetype: Archetype) -> str:
    payload: dict[str, Any] = {
        "detected_archetype": archetype,
        "job_description": req.jd.text,
        "profile_seed": req.resume.profile_seed,
        "experiences": [
            {
                "id": e.id,
                "title": e.title,
                "company": e.company,
                "start": e.start,
                "end": e.end,
                "bullets": [
                    {"id": s.id, "text": s.text, "keywords": s.keywords} for s in e.stories
                ],
            }
            for e in req.resume.experiences
        ],
        "skills_pool": req.resume.skills,
        "tiebreaker_preference": req.settings.tiebreaker,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


async def tailor_ai(req: TailorRequest, *, client: AsyncOpenAI) -> TailorResult:
    archetype: Archetype = req.jd.archetype_override or detect_archetype(req.jd.text)
    system_prompt = _PROMPT_PATH.read_text()
    user_prompt = _user_prompt(req, archetype)
    model = os.getenv("OPENAI_MODEL", _DEFAULT_MODEL)
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT)))

    t0 = time.monotonic()
    response = await client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=_AIResponse,
        timeout=timeout,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    parsed = response.choices[0].message.parsed
    if parsed is None:
        # OpenAI returned a refusal or an unparseable result.
        log.warning("openai returned no parseable result; falling back to stub")
        from .tailor import tailor_stub  # avoid circular import at module load

        return tailor_stub(req)

    pool_by_exp = {exp.id: {s.id for s in exp.stories} for exp in req.resume.experiences}
    cleaned, dropped = validate_experiences(parsed.experiences, pool_by_exp)
    profile, fallback = validate_profile(parsed.profile, req.resume.profile_seed)

    log.info(
        "tailor_ai",
        extra={
            "archetype": archetype,
            "stories_in": sum(len(e.stories) for e in req.resume.experiences),
            "stories_picked": sum(len(c.story_ids) for c in cleaned),
            "profile_words": len(profile.split()),
            "openai_latency_ms": latency_ms,
            "dropped_count": len(dropped),
            "profile_fallback": fallback,
        },
    )

    return TailorResult(
        profile=profile,
        experiences=cleaned,
        skills=parsed.skills,
        archetype_used=archetype,
        keywords_injected=parsed.keywords_injected,
        dropped_story_ids=dropped,
        profile_fallback_used=fallback,
    )
