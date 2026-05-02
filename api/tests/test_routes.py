from __future__ import annotations

from typing import Any

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_healthz() -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["pdf"] is True
    assert isinstance(body["openai"], bool)


def test_tailor_smoke_camelcase_wire() -> None:
    # Wire format is camelCase. Pydantic accepts snake_case too thanks to
    # populate_by_name=True, but the canonical request and response both
    # use camelCase to match the eventual generated TS types.
    payload: dict[str, Any] = {
        "resume": {
            "contact": {"name": "Ada", "email": "ada@example.com"},
            "profileSeed": (
                "Backend engineer who cares about clean APIs and observability across the stack."
            ),
            "experiences": [
                {
                    "id": "e1",
                    "company": "Co",
                    "title": "Engineer",
                    "start": "2022",
                    "stories": [
                        {"id": "s1", "text": "Owned the API.", "keywords": ["api"]},
                        {"id": "s2", "text": "Mentored peers.", "keywords": ["mentoring"]},
                    ],
                }
            ],
            "skills": ["Python", "Postgres"],
        },
        "jd": {"text": "Backend engineer to own a payments API. Python and Postgres required."},
    }
    r = client.post("/api/tailor", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["archetypeUsed"] == "backend"
    assert body["experiences"][0]["storyIds"][0] == "s1"
    assert body["experiences"][0]["experienceId"] == "e1"
    assert body["skills"] == ["Python", "Postgres"]
    # Sanity: snake_case keys should not appear in the response.
    assert "archetype_used" not in body
    assert "story_ids" not in body["experiences"][0]


def test_tailor_accepts_snake_case_input() -> None:
    # populate_by_name=True means the API stays friendly to snake_case
    # callers (e.g. curl examples in docs). The response is still camelCase.
    payload: dict[str, Any] = {
        "resume": {
            "contact": {"name": "Ada", "email": "ada@example.com"},
            "profile_seed": (
                "Backend engineer who cares about clean APIs and observability across the stack."
            ),
            "experiences": [
                {
                    "id": "e1",
                    "company": "Co",
                    "title": "Engineer",
                    "start": "2022",
                    "stories": [{"id": "s1", "text": "Owned the API.", "keywords": ["api"]}],
                }
            ],
        },
        "jd": {"text": "Backend engineer to own a payments API. Python and Postgres required."},
    }
    r = client.post("/api/tailor", json=payload)
    assert r.status_code == 200, r.text


def test_tailor_rejects_unknown_field() -> None:
    # extra="forbid" everywhere — typos surface, not silently dropped.
    r = client.post(
        "/api/tailor",
        json={
            "resume": {
                "contact": {"name": "X", "email": "x@example.com", "bogus": "field"},
                "profileSeed": "Some seed describing the candidate at sufficient length.",
                "experiences": [
                    {
                        "id": "e1",
                        "company": "Co",
                        "title": "Engineer",
                        "start": "2022",
                        "stories": [{"id": "s1", "text": "Did stuff."}],
                    }
                ],
            },
            "jd": {"text": "Looking for an engineer with at least fifty characters of JD."},
        },
    )
    assert r.status_code == 422


def test_tailor_rejects_invalid_month() -> None:
    # PartialDate now constrains months to 01-12.
    r = client.post(
        "/api/tailor",
        json={
            "resume": {
                "contact": {"name": "X", "email": "x@example.com"},
                "profileSeed": "Some seed describing the candidate at sufficient length.",
                "experiences": [
                    {
                        "id": "e1",
                        "company": "Co",
                        "title": "Engineer",
                        "start": "2022-13",
                        "stories": [{"id": "s1", "text": "Did stuff."}],
                    }
                ],
            },
            "jd": {"text": "Looking for an engineer with at least fifty characters of JD."},
        },
    )
    assert r.status_code == 422


def test_tailor_rejects_empty_keyword() -> None:
    # Per-item Keyword constraint: min_length=1, max_length=60.
    r = client.post(
        "/api/tailor",
        json={
            "resume": {
                "contact": {"name": "X", "email": "x@example.com"},
                "profileSeed": "Some seed describing the candidate at sufficient length.",
                "experiences": [
                    {
                        "id": "e1",
                        "company": "Co",
                        "title": "Engineer",
                        "start": "2022",
                        "stories": [{"id": "s1", "text": "Did stuff.", "keywords": [""]}],
                    }
                ],
            },
            "jd": {"text": "Looking for an engineer with at least fifty characters of JD."},
        },
    )
    assert r.status_code == 422
