"""Audit the bullet-pool contract on a worked example.

Reads a `ResumeInput` JSON, the JD it was tailored against, and the
`TailorResult` JSON produced by the pipeline, and asserts:

* every selected story ID maps to a real bullet in the input pool;
* every output skill exists (case-insensitively) in the input skill list;
* the profile paragraph respects the documented guardrails
  (45-75 words, no banned phrases, no em-dashes / `--`);
* the archetype is one of the documented values;
* dropped IDs and profile fallbacks are surfaced (not silently swallowed).

The point of this script is *external* verification: it imports nothing
from `app.*`, so a regression in the production validators that breaks
the contract on the worked example will be caught here even if the
internal unit tests still pass.

Usage::

    python evals/check_provenance.py
    python evals/check_provenance.py --resume path.json --tailored other.json

Exits 0 on success, 1 on any contract violation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# JSON shapes are intentionally typed as `dict[str, Any]` rather than imported
# from `app.domain.models`: the eval is an external auditor and must not
# depend on the production code it's validating.
Json = dict[str, Any]

# These constants are duplicated from the production code on purpose:
# the eval should fail loudly if production drifts out of sync with what
# the README and CLAUDE.md promise. Update both deliberately, never
# silently.
PROFILE_MIN_WORDS = 45
PROFILE_MAX_WORDS = 75
BANNED_PHRASES = (
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
ALLOWED_ARCHETYPES = (
    "backend",
    "frontend",
    "fullstack",
    "data",
    "ml",
    "platform",
    "mobile",
    "generalist",
)

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> Json:
    data: Json = json.loads(path.read_text())
    return data


def check_story_provenance(resume: Json, tailored: Json) -> list[str]:
    failures: list[str] = []
    pool: dict[str, set[str]] = {
        exp["id"]: {s["id"] for s in exp.get("stories", [])} for exp in resume["experiences"]
    }
    for tailored_exp in tailored["experiences"]:
        exp_id = tailored_exp["experienceId"]
        if exp_id not in pool:
            failures.append(f"experienceId not in input pool: {exp_id!r}")
            continue
        for sid in tailored_exp["storyIds"]:
            if sid not in pool[exp_id]:
                failures.append(f"story {sid!r} not in input pool for experience {exp_id!r}")
    return failures


def check_skill_provenance(resume: Json, tailored: Json) -> list[str]:
    input_skills = {s.lower() for s in resume.get("skills", [])}
    failures: list[str] = []
    for s in tailored.get("skills", []):
        if s.lower() not in input_skills:
            failures.append(f"skill {s!r} not in input skill pool")
    return failures


def check_profile(tailored: Json) -> list[str]:
    failures: list[str] = []
    profile = tailored["profile"]
    if "—" in profile:
        failures.append("profile contains an em-dash (—)")
    if "--" in profile:
        failures.append("profile contains '--'")
    lower = profile.lower()
    hits = [p for p in BANNED_PHRASES if p in lower]
    if hits:
        failures.append(f"profile contains banned phrases: {hits}")
    word_count = len(profile.split())
    if not (PROFILE_MIN_WORDS <= word_count <= PROFILE_MAX_WORDS):
        failures.append(
            f"profile word count {word_count} outside [{PROFILE_MIN_WORDS}, {PROFILE_MAX_WORDS}]"
        )
    return failures


def check_archetype(tailored: Json) -> list[str]:
    a = tailored.get("archetypeUsed")
    if a not in ALLOWED_ARCHETYPES:
        return [f"archetypeUsed {a!r} not in allowed set {ALLOWED_ARCHETYPES}"]
    return []


def report(label: str, failures: list[str], total: int | None = None) -> bool:
    """Print a one-line PASS/FAIL header plus indented details. Return ok-bool."""
    ok = not failures
    suffix = ""
    if total is not None:
        suffix = f" ({total - len(failures)}/{total} ok)"
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{suffix}")
    for f in failures:
        print(f"         - {f}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume",
        type=Path,
        default=ROOT / "examples" / "sample-resume.json",
    )
    parser.add_argument(
        "--tailored",
        type=Path,
        default=ROOT / "examples" / "tailored.json",
    )
    args = parser.parse_args()

    resume = load(args.resume)
    tailored = load(args.tailored)

    print(f"Auditing {args.tailored.relative_to(ROOT)} against {args.resume.relative_to(ROOT)}\n")

    total_stories = sum(len(e["storyIds"]) for e in tailored["experiences"])
    total_skills = len(tailored.get("skills", []))

    checks = [
        (
            "story IDs grounded in input pool",
            check_story_provenance(resume, tailored),
            total_stories,
        ),
        ("skills grounded in input pool", check_skill_provenance(resume, tailored), total_skills),
        ("profile paragraph guardrails", check_profile(tailored), None),
        ("archetypeUsed is allowed", check_archetype(tailored), None),
    ]

    all_ok = True
    for label, failures, total in checks:
        all_ok &= report(label, failures, total)

    dropped = tailored.get("droppedStoryIds", [])
    fallback = tailored.get("profileFallbackUsed", False)
    print()
    print(f"  droppedStoryIds: {len(dropped)} {dropped if dropped else ''}".rstrip())
    print(f"  profileFallbackUsed: {fallback}")
    print()

    if all_ok:
        print("OK — bullet-pool contract holds on this example.")
        return 0
    print("FAIL — at least one contract violation above.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
