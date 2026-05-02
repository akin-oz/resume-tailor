"""Shared fixtures: a minimal-but-real ResumeInput we can mutate per test."""

from __future__ import annotations

import pytest
from app.domain.models import (
    Contact,
    Experience,
    JobDescription,
    ResumeInput,
    Story,
    TailorRequest,
    TailorSettings,
)


def make_story(sid: str, text: str, keywords: list[str] | None = None) -> Story:
    return Story(id=sid, text=text, keywords=keywords or [])


@pytest.fixture
def resume() -> ResumeInput:
    return ResumeInput(
        contact=Contact(name="Ada Lovelace", email="ada@example.com"),
        profile_seed=(
            "Backend engineer with eight years building payment platforms. "
            "Led teams of three to seven, owned services from design through "
            "production rollout, and care a lot about clean APIs and "
            "observability."
        ),
        experiences=[
            Experience(
                id="exp1",
                company="Acme",
                title="Senior Engineer",
                start="2021-01",
                stories=[
                    make_story(
                        "s1",
                        "Designed payments API used by 12 internal services.",
                        keywords=["api design", "ownership"],
                    ),
                    make_story(
                        "s2",
                        "Mentored two engineers through promotion.",
                        keywords=["mentoring", "leadership"],
                    ),
                    make_story(
                        "s3",
                        "Cut p99 latency 40% by rewriting the auth path.",
                        keywords=["performance"],
                    ),
                    make_story(
                        "s4",
                        "Wrote the team's incident playbook.",
                        keywords=[],
                    ),
                ],
            ),
        ],
        skills=["Python", "PostgreSQL", "Kubernetes", "FastAPI"],
    )


@pytest.fixture
def jd_backend() -> JobDescription:
    return JobDescription(
        text=(
            "We're hiring a senior backend engineer to own our payments API. "
            "You'll mentor a small team, drive API design, and ensure "
            "reliability via good observability. Python and PostgreSQL "
            "experience required; FastAPI a plus."
        )
    )


def make_request(
    resume: ResumeInput,
    jd: JobDescription,
    settings: TailorSettings | None = None,
) -> TailorRequest:
    return TailorRequest(resume=resume, jd=jd, settings=settings or TailorSettings())
