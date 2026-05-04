"""Pytest wrapper around `check_provenance` so `make check` covers it.

Two layers:

1. **Worked-example regression** — load the committed example outputs
   and assert every contract check passes. A regression in the
   production tailor that breaks the contract on the public worked
   example will fail this test.

2. **Negative tests** — feed each check function deliberately broken
   input and assert it returns the expected failure. This proves the
   auditor itself isn't a no-op.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from check_provenance import (
    Json,
    check_archetype,
    check_profile,
    check_skill_provenance,
    check_story_provenance,
)

ROOT = Path(__file__).resolve().parents[1]
RESUME_PATH = ROOT / "examples" / "sample-resume.json"
TAILORED_PATH = ROOT / "examples" / "tailored.json"


@pytest.fixture(scope="module")
def resume() -> Json:
    data: Json = json.loads(RESUME_PATH.read_text())
    return data


@pytest.fixture(scope="module")
def tailored() -> Json:
    data: Json = json.loads(TAILORED_PATH.read_text())
    return data


# --- Worked example: every check passes ---------------------------------


def test_worked_example_story_provenance(resume: Json, tailored: Json) -> None:
    assert check_story_provenance(resume, tailored) == []


def test_worked_example_skill_provenance(resume: Json, tailored: Json) -> None:
    assert check_skill_provenance(resume, tailored) == []


def test_worked_example_profile(tailored: Json) -> None:
    assert check_profile(tailored) == []


def test_worked_example_archetype(tailored: Json) -> None:
    assert check_archetype(tailored) == []


# --- Negative tests: broken input is detected ---------------------------


def test_story_check_catches_invented_id(resume: Json, tailored: Json) -> None:
    bad = copy.deepcopy(tailored)
    bad["experiences"][0]["storyIds"].append("s-not-in-pool")
    failures = check_story_provenance(resume, bad)
    assert any("s-not-in-pool" in f for f in failures)


def test_story_check_catches_invented_experience(resume: Json, tailored: Json) -> None:
    bad = copy.deepcopy(tailored)
    bad["experiences"].append({"experienceId": "exp-fabricated", "storyIds": []})
    failures = check_story_provenance(resume, bad)
    assert any("exp-fabricated" in f for f in failures)


def test_skill_check_catches_invented_skill(resume: Json, tailored: Json) -> None:
    bad = copy.deepcopy(tailored)
    bad["skills"].append("Rust (invented)")
    failures = check_skill_provenance(resume, bad)
    assert any("Rust" in f for f in failures)


def test_profile_check_catches_em_dash(tailored: Json) -> None:
    bad = copy.deepcopy(tailored)
    bad["profile"] = bad["profile"] + " — fluff."
    failures = check_profile(bad)
    assert any("em-dash" in f for f in failures)


def test_profile_check_catches_banned_phrase(tailored: Json) -> None:
    bad = copy.deepcopy(tailored)
    bad["profile"] = bad["profile"] + " I am passionate about engineering."
    failures = check_profile(bad)
    assert any("banned" in f for f in failures)


def test_profile_check_catches_short_profile(tailored: Json) -> None:
    bad = copy.deepcopy(tailored)
    bad["profile"] = "Too short."
    failures = check_profile(bad)
    assert any("word count" in f for f in failures)


def test_archetype_check_catches_unknown(tailored: Json) -> None:
    bad = copy.deepcopy(tailored)
    bad["archetypeUsed"] = "wizard"
    failures = check_archetype(bad)
    assert any("wizard" in f for f in failures)
