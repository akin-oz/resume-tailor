from __future__ import annotations

from app.domain.models import (
    Contact,
    Experience,
    JobDescription,
    ResumeInput,
    TailorSettings,
)
from app.domain.tailor import tailor_stub

from .conftest import make_request, make_story


def test_keyword_overlap_ranks_first(resume: ResumeInput, jd_backend: JobDescription) -> None:
    result = tailor_stub(make_request(resume, jd_backend))
    picked = result.experiences[0].story_ids
    # s1 has "api design" + "ownership"; s2 has "mentoring" + "leadership".
    # JD mentions API design and mentoring → both score, s1 first by input order.
    assert picked[0] == "s1"
    assert "s2" in picked
    # s4 has no keywords; ranks last but still inside the per-role cap of 4.
    assert picked[-1] == "s4"


def test_zero_match_falls_back_to_input_order(resume: ResumeInput) -> None:
    irrelevant = JobDescription(
        text=(
            "Hardware firmware role for embedded controllers. C, RTOS, "
            "soldering bench experience. Sensors and actuators."
        )
    )
    result = tailor_stub(make_request(resume, irrelevant))
    assert result.experiences[0].story_ids == ["s1", "s2", "s3", "s4"]


def test_length_desc_tiebreaker(jd_backend: JobDescription) -> None:
    # Two same-keyword bullets; the longer one should win.
    resume = ResumeInput(
        contact=Contact(name="X", email="x@example.com"),
        profile_seed="A short profile seed describing the candidate's work.",
        experiences=[
            Experience(
                id="e1",
                company="Co",
                title="Engineer",
                start="2022",
                stories=[
                    make_story("short", "Owned API.", keywords=["api"]),
                    make_story(
                        "long",
                        "Owned the public payments API end-to-end across two quarters.",
                        keywords=["api"],
                    ),
                ],
            )
        ],
    )
    result = tailor_stub(make_request(resume, jd_backend, TailorSettings(tiebreaker="length_desc")))
    assert result.experiences[0].story_ids == ["long", "short"]


def test_length_asc_tiebreaker(jd_backend: JobDescription) -> None:
    resume = ResumeInput(
        contact=Contact(name="X", email="x@example.com"),
        profile_seed="A short profile seed describing the candidate's work.",
        experiences=[
            Experience(
                id="e1",
                company="Co",
                title="Engineer",
                start="2022",
                stories=[
                    make_story(
                        "long",
                        "Owned the public payments API end-to-end across two quarters.",
                        keywords=["api"],
                    ),
                    make_story("short", "Owned API.", keywords=["api"]),
                ],
            )
        ],
    )
    result = tailor_stub(make_request(resume, jd_backend, TailorSettings(tiebreaker="length_asc")))
    assert result.experiences[0].story_ids == ["short", "long"]


def test_archetype_override_is_honored(resume: ResumeInput, jd_backend: JobDescription) -> None:
    jd = jd_backend.model_copy(update={"archetype_override": "frontend"})
    result = tailor_stub(make_request(resume, jd))
    assert result.archetype_used == "frontend"


def test_skills_reordered_by_jd_match(resume: ResumeInput, jd_backend: JobDescription) -> None:
    result = tailor_stub(make_request(resume, jd_backend))
    # JD names Python, PostgreSQL, FastAPI — Kubernetes is unmatched, so it
    # falls to the end. Matched skills keep their input order.
    assert result.skills == ["Python", "PostgreSQL", "FastAPI", "Kubernetes"]


def test_profile_truncated_to_word_cap() -> None:
    seed = " ".join(f"x{i}" for i in range(120))
    resume = ResumeInput(
        contact=Contact(name="X", email="x@example.com"),
        profile_seed=seed,
        experiences=[
            Experience(
                id="e1",
                company="Co",
                title="Engineer",
                start="2022",
                stories=[make_story("s1", "Did things.")],
            )
        ],
    )
    result = tailor_stub(
        make_request(
            resume,
            JobDescription(
                text="A perfectly ordinary job description used for the truncation test."
            ),
        )
    )
    assert len(result.profile.split()) <= 75


def test_keywords_injected_only_when_matched(
    resume: ResumeInput, jd_backend: JobDescription
) -> None:
    result = tailor_stub(make_request(resume, jd_backend))
    # s1's "api design" matches; "performance" (s3) does not appear in this JD.
    assert "api design" in result.keywords_injected
    assert "performance" not in result.keywords_injected


def test_dropped_story_ids_empty_in_stub_mode(
    resume: ResumeInput, jd_backend: JobDescription
) -> None:
    # Stub mode picks from a known pool; nothing to drop.
    result = tailor_stub(make_request(resume, jd_backend))
    assert result.dropped_story_ids == []
    assert result.profile_fallback_used is False
