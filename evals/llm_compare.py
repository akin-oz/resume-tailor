"""Stage-2 eval: unconstrained vs bullet-pool tailoring on the worked example.

Runs the same input (`examples/sample-resume.json` + `examples/sample-jd.txt`)
through two paths and compares fabrication rates:

1. **Unconstrained** — passes the candidate facts + JD to the model and
   asks it to write a tailored resume freehand. No bullet pool, no
   ID-only contract, no validators. This is the baseline behaviour you
   get from "ask ChatGPT to write me a resume".

2. **Constrained (bullet-pool)** — the production `tailor_ai` pipeline:
   model returns IDs only, server-side validators drop unknown IDs,
   profile is checked against banned phrases and the 45-75 word window
   with fallback to a clean truncation of `profile_seed`.

For each output we count:

* **Numeric claims fabricated** — every number-token in the output that
  doesn't appear in the input pool. Invented metrics are the most
  damning hallucination on a resume; the bullet-pool contract makes
  these mechanically impossible.
* **Skills fabricated** — output skills not in the input skill list.
* **Profile guardrail violations** — banned phrases, em-dashes,
  word-count window.

Writes `evals/results/llm_compare.md` (human-readable report) and
`evals/results/llm_compare.json` (raw outputs for reproducibility).

Gated on `OPENAI_API_KEY` — does NOT run as part of `make check`.
Manual invocation only::

    OPENAI_API_KEY=sk-... make eval-llm
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.domain.models import ResumeInput, TailorRequest  # noqa: E402
from app.domain.tailor_ai import tailor_ai  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from pydantic import BaseModel, ConfigDict  # noqa: E402

EXAMPLES = ROOT / "examples"
RESULTS = ROOT / "evals" / "results"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Numeric tokens we treat as factual claims that must trace to the input.
# Captures things like "400K", "39%", "65%", "9+", "14 tagged releases",
# "$30M". Pure punctuation/years-only matches are kept too so we can
# diff them against the input pool.
NUMBER_RE = re.compile(r"\$?\d+(?:[.,]\d+)?(?:[KMB%x]|\+|\s*-\s*\d+)?", re.IGNORECASE)

BANNED = (
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


# --- Unconstrained-mode response shape -----------------------------------


class _UnconstrainedExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: str
    title: str
    bullets: list[str]


class _UnconstrainedResume(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: str
    experiences: list[_UnconstrainedExperience]
    skills: list[str]


_UNCONSTRAINED_SYSTEM = (
    "You are a resume writer. Given the candidate's background and a job "
    "description, write a tailored resume that maximises their chances. "
    "Pick the most impressive accomplishments, quantify outcomes wherever "
    "you can, and use vocabulary from the job description. Output JSON "
    "matching the provided schema."
)


async def _run_unconstrained(
    client: AsyncOpenAI, resume_data: dict[str, Any], jd_text: str
) -> _UnconstrainedResume:
    """Ask the model to write a resume freehand. The eval baseline."""
    user_prompt = json.dumps(
        {
            "candidate_summary": resume_data["profileSeed"],
            "experience_summary": [
                {
                    "company": e["company"],
                    "title": e["title"],
                    "start": e.get("start"),
                    "end": e.get("end"),
                    # Pass the bullets as background context so the model has the
                    # facts; it's still allowed to write whatever it wants.
                    "background_notes": [s["text"] for s in e.get("stories", [])],
                }
                for e in resume_data["experiences"]
            ],
            "candidate_skills": resume_data.get("skills", []),
            "job_description": jd_text,
        },
        ensure_ascii=False,
    )
    response = await client.beta.chat.completions.parse(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": _UNCONSTRAINED_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        response_format=_UnconstrainedResume,
    )
    parsed = response.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("unconstrained model returned no parseable result")
    return parsed


# --- Fabrication detection -----------------------------------------------


def _input_corpus(resume_data: dict[str, Any]) -> str:
    """All input text (profile + bullets + skills) concatenated, lowercased."""
    parts = [resume_data.get("profileSeed", "")]
    parts.extend(s["text"] for e in resume_data["experiences"] for s in e.get("stories", []))
    parts.extend(resume_data.get("skills", []))
    return " ".join(parts).lower()


def _input_skill_set(resume_data: dict[str, Any]) -> set[str]:
    return {s.lower() for s in resume_data.get("skills", [])}


def _numbers_in(text: str) -> list[str]:
    """Numeric claims as they appear in text, lowercased and stripped."""
    return [m.group(0).lower().strip() for m in NUMBER_RE.finditer(text)]


def _fabricated_numbers(output_text: str, corpus: str) -> list[str]:
    out = _numbers_in(output_text)
    in_corpus = set(_numbers_in(corpus))
    return [n for n in out if n not in in_corpus]


def _profile_violations(profile: str) -> list[str]:
    out: list[str] = []
    if "—" in profile:
        out.append("em-dash present")
    if "--" in profile:
        out.append("'--' present")
    lower = profile.lower()
    hits = [b for b in BANNED if b in lower]
    if hits:
        out.append(f"banned phrases: {hits}")
    wc = len(profile.split())
    if not (45 <= wc <= 75):
        out.append(f"word count {wc} outside [45, 75]")
    return out


# --- Comparison + report --------------------------------------------------


def _summarise(
    label: str,
    profile: str,
    bullets: list[str],
    skills: list[str],
    resume_data: dict[str, Any],
) -> dict[str, Any]:
    corpus = _input_corpus(resume_data)
    bullet_text = " ".join(bullets)
    profile_text = profile
    skill_pool = _input_skill_set(resume_data)
    return {
        "label": label,
        "profile_word_count": len(profile.split()),
        "profile_violations": _profile_violations(profile),
        "bullets_emitted": len(bullets),
        "bullet_numbers_fabricated": _fabricated_numbers(bullet_text, corpus),
        "profile_numbers_fabricated": _fabricated_numbers(profile_text, corpus),
        "skills_emitted": len(skills),
        "skills_fabricated": [s for s in skills if s.lower() not in skill_pool],
    }


def _markdown_report(unconstrained: dict[str, Any], constrained: dict[str, Any]) -> str:
    def fmt_list(xs: list[str]) -> str:
        return ", ".join(f"`{x}`" for x in xs) if xs else "—"

    rows = [
        ("bullets emitted", unconstrained["bullets_emitted"], constrained["bullets_emitted"]),
        ("skills emitted", unconstrained["skills_emitted"], constrained["skills_emitted"]),
        (
            "skills fabricated",
            len(unconstrained["skills_fabricated"]),
            len(constrained["skills_fabricated"]),
        ),
        (
            "numeric claims fabricated (bullets)",
            len(unconstrained["bullet_numbers_fabricated"]),
            len(constrained["bullet_numbers_fabricated"]),
        ),
        (
            "numeric claims fabricated (profile)",
            len(unconstrained["profile_numbers_fabricated"]),
            len(constrained["profile_numbers_fabricated"]),
        ),
        (
            "profile word count",
            unconstrained["profile_word_count"],
            constrained["profile_word_count"],
        ),
        (
            "profile guardrail violations",
            len(unconstrained["profile_violations"]),
            len(constrained["profile_violations"]),
        ),
    ]

    md = ["# LLM compare — unconstrained vs bullet-pool", ""]
    md.append(f"Model: `{DEFAULT_MODEL}`")
    md.append(
        "Inputs: `examples/sample-resume.json` + `examples/sample-jd.txt` "
        "(Lette, Senior Product Engineer)."
    )
    md.append("")
    md.append("| Metric | Unconstrained | Bullet-pool |")
    md.append("|---|---:|---:|")
    for label, u, c in rows:
        md.append(f"| {label} | {u} | {c} |")
    md.append("")
    md.append("## Fabricated numeric claims")
    md.append("")
    md.append(
        "**Unconstrained (bullets):** " + fmt_list(unconstrained["bullet_numbers_fabricated"])
    )
    md.append(
        "**Unconstrained (profile):** " + fmt_list(unconstrained["profile_numbers_fabricated"])
    )
    md.append("**Bullet-pool (bullets):** " + fmt_list(constrained["bullet_numbers_fabricated"]))
    md.append("**Bullet-pool (profile):** " + fmt_list(constrained["profile_numbers_fabricated"]))
    md.append("")
    md.append("## Fabricated skills")
    md.append("")
    md.append("**Unconstrained:** " + fmt_list(unconstrained["skills_fabricated"]))
    md.append("**Bullet-pool:** " + fmt_list(constrained["skills_fabricated"]))
    md.append("")
    md.append("## Profile guardrail violations")
    md.append("")
    md.append("**Unconstrained:** " + fmt_list(unconstrained["profile_violations"]))
    md.append("**Bullet-pool:** " + fmt_list(constrained["profile_violations"]))
    md.append("")
    md.append("## How to read this")
    md.append("")
    md.append(
        "A *fabricated numeric claim* is a number that appears in the output but "
        "nowhere in the input pool (the candidate's verified bullets, profile "
        "seed, or skill list). On a resume, an invented metric is the most "
        "damaging form of hallucination — the unconstrained baseline shows what "
        "happens without guardrails."
    )
    md.append("")
    md.append(
        "The bullet-pool contract makes invented metrics in *bullets* "
        "mechanically impossible (the bullet text is reused verbatim from the "
        "input pool, never rewritten). Profile metrics are still possible in "
        "principle, but the 45-75 word window plus banned-phrase filter plus "
        "fallback to `profile_seed` truncation push the count toward zero in "
        "practice."
    )
    return "\n".join(md) + "\n"


# --- Entry point ----------------------------------------------------------


async def _run() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set — skipping. (eval is key-gated)", file=sys.stderr)
        return 2

    resume_data = json.loads((EXAMPLES / "sample-resume.json").read_text())
    jd_text = (EXAMPLES / "sample-jd.txt").read_text()
    client = AsyncOpenAI()

    print(f"running unconstrained ({DEFAULT_MODEL})...")
    unconstrained_out = await _run_unconstrained(client, resume_data, jd_text)

    print(f"running constrained tailor_ai ({DEFAULT_MODEL})...")
    req = TailorRequest.model_validate({"resume": resume_data, "jd": {"text": jd_text}})
    constrained_result = await tailor_ai(req, client=client)
    resume = ResumeInput.model_validate(resume_data)

    # Resolve the constrained output's storyIds back to bullet texts so we can
    # diff them on equal terms with the unconstrained free-text bullets.
    bullet_lookup = {s.id: s.text for e in resume.experiences for s in e.stories}
    constrained_bullets = [
        bullet_lookup[sid]
        for tx in constrained_result.experiences
        for sid in tx.story_ids
        if sid in bullet_lookup
    ]
    unconstrained_bullets = [b for e in unconstrained_out.experiences for b in e.bullets]

    unc_summary = _summarise(
        "unconstrained",
        unconstrained_out.profile,
        unconstrained_bullets,
        unconstrained_out.skills,
        resume_data,
    )
    con_summary = _summarise(
        "bullet-pool",
        constrained_result.profile,
        constrained_bullets,
        constrained_result.skills,
        resume_data,
    )

    RESULTS.mkdir(exist_ok=True)
    md = _markdown_report(unc_summary, con_summary)
    (RESULTS / "llm_compare.md").write_text(md)
    raw = {
        "model": DEFAULT_MODEL,
        "summary": {"unconstrained": unc_summary, "bullet_pool": con_summary},
        "outputs": {
            "unconstrained": unconstrained_out.model_dump(),
            "bullet_pool": constrained_result.model_dump(by_alias=True),
        },
    }
    (RESULTS / "llm_compare.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n")

    print("\n" + md)
    print(f"wrote {(RESULTS / 'llm_compare.md').relative_to(ROOT)}")
    print(f"wrote {(RESULTS / 'llm_compare.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_run()))
