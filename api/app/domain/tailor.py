"""Stub-mode tailor: deterministic, no I/O, no API key required.

When ``OPENAI_API_KEY`` is unset (and in tests), this is the implementation
behind ``POST /api/tailor``. The output shape is identical to the AI path,
so the frontend has a single contract.

Ranking rules:

* **Bullets** — score = count of user-tagged keywords that match the JD.
  Multi-word keywords (``"product management"``) use case-insensitive
  substring match against the raw JD text. Single-token keywords match
  whole words against a tokenized JD set, so ``"go"`` doesn't match
  ``"goal"``. Bullets with no keywords score 0 and rank last.
* **Tiebreaker** — controlled by ``TailorSettings.tiebreaker``. Default
  is input order (predictable, test-friendly, matches the user's
  implicit prioritization).
* **Skills** — same JD-overlap idea. Matched first, original order
  preserved within each group.
* **Profile** — clean truncation of ``profile_seed`` to <=75 words,
  preferring a sentence boundary in the second half if one exists.
"""

from __future__ import annotations

import re

from .archetype import detect_archetype
from .models import (
    Story,
    TailoredExperience,
    TailorRequest,
    TailorResult,
    TailorSettings,
)

_MAX_BULLETS_PER_ROLE = 4
_PROFILE_MAX_WORDS = 75

# Token = lowercase word starting with a letter, length >= 3, allowing a
# few common in-word symbols (c++, node.js, fine-tuning). 2-char names
# like c# and go are below the floor; users should tag those bullets
# with the full name ("csharp", "golang") instead.
_TOKEN_RE = re.compile(r"[a-z][a-z+#./\-]{2,}")


def _index_jd(text: str) -> tuple[set[str], str]:
    lower = text.lower()
    return set(_TOKEN_RE.findall(lower)), lower


def _matches_jd(term: str, jd_tokens: set[str], jd_lower: str) -> bool:
    t = term.strip().lower()
    if not t:
        return False
    if " " in t:
        return t in jd_lower
    return t in jd_tokens


def _score(story: Story, jd_tokens: set[str], jd_lower: str) -> int:
    return sum(1 for kw in story.keywords if _matches_jd(kw, jd_tokens, jd_lower))


def _sort_key(
    story: Story,
    idx: int,
    settings: TailorSettings,
    jd_tokens: set[str],
    jd_lower: str,
) -> tuple[int, int, int]:
    # Negative score so higher scores sort first.
    score = -_score(story, jd_tokens, jd_lower)
    if settings.tiebreaker == "length_desc":
        return (score, -len(story.text), idx)
    if settings.tiebreaker == "length_asc":
        return (score, len(story.text), idx)
    return (score, idx, 0)


def _truncate_profile(seed: str, max_words: int = _PROFILE_MAX_WORDS) -> str:
    words = seed.split()
    if len(words) <= max_words:
        return seed.strip()
    truncated = " ".join(words[:max_words])
    for terminator in (". ", "! ", "? "):
        idx = truncated.rfind(terminator)
        if idx > len(truncated) // 2:
            return truncated[: idx + 1].strip()
    return truncated.rstrip(",;:") + "."


def tailor_stub(req: TailorRequest) -> TailorResult:
    jd_tokens, jd_lower = _index_jd(req.jd.text)
    archetype = req.jd.archetype_override or detect_archetype(req.jd.text)

    tailored: list[TailoredExperience] = []
    keywords_injected: list[str] = []
    seen: set[str] = set()

    for exp in req.resume.experiences:
        ranked = sorted(
            enumerate(exp.stories),
            key=lambda pair: _sort_key(pair[1], pair[0], req.settings, jd_tokens, jd_lower),
        )
        picked = [story for _, story in ranked[:_MAX_BULLETS_PER_ROLE]]
        tailored.append(TailoredExperience(experience_id=exp.id, story_ids=[s.id for s in picked]))
        for story in picked:
            for kw in story.keywords:
                k = kw.strip().lower()
                if k and k not in seen and _matches_jd(k, jd_tokens, jd_lower):
                    keywords_injected.append(k)
                    seen.add(k)

    skills_indexed = list(enumerate(req.resume.skills))
    skills_sorted = [
        skill
        for _, skill in sorted(
            skills_indexed,
            key=lambda pair: (
                0 if _matches_jd(pair[1], jd_tokens, jd_lower) else 1,
                pair[0],
            ),
        )
    ]

    return TailorResult(
        profile=_truncate_profile(req.resume.profile_seed),
        experiences=tailored,
        skills=skills_sorted,
        archetype_used=archetype,
        keywords_injected=keywords_injected,
        dropped_story_ids=[],
        profile_fallback_used=False,
    )
