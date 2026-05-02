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
    assert body["playwright"] is False
    assert isinstance(body["openai"], bool)


def test_tailor_smoke() -> None:
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
    assert body["archetype_used"] == "backend"
    assert body["experiences"][0]["story_ids"][0] == "s1"
    assert body["skills"] == ["Python", "Postgres"]


def test_tailor_rejects_unknown_field() -> None:
    # extra="forbid" everywhere — typos surface, not silently dropped.
    r = client.post(
        "/api/tailor",
        json={
            "resume": {
                "contact": {"name": "X", "email": "x@example.com", "bogus": "field"},
                "profile_seed": "Some seed describing the candidate at sufficient length.",
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
