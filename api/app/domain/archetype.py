"""Lightweight archetype detection by keyword frequency.

The point isn't taxonomic correctness — it's giving the AI (and the user)
a one-word category for the JD so the tailor can lean toward the right
kinds of bullets. Users can override via the UI; the heuristic is just
the default.
"""

from __future__ import annotations

from .models import Archetype

# Phrases / tokens that signal each archetype. Substring match,
# case-insensitive. Multi-word phrases are matched verbatim.
_SIGNALS: dict[Archetype, tuple[str, ...]] = {
    "frontend": (
        "react",
        "vue",
        "angular",
        "svelte",
        "next.js",
        "tailwind",
        "css",
        "html",
        "front end",
        "front-end",
        "frontend",
        "ui engineer",
        "ux engineer",
        "browser",
        "responsive",
    ),
    "backend": (
        "back end",
        "back-end",
        "backend",
        "rest api",
        "graphql api",
        "grpc",
        "microservice",
        "fastapi",
        "django",
        "flask",
        "spring boot",
        "rails",
        "node.js",
        "postgres",
        "mysql",
        "mongodb",
        "redis",
        "kafka",
    ),
    "fullstack": (
        "full stack",
        "fullstack",
        "full-stack",
        "end to end",
        "end-to-end",
    ),
    "data": (
        "etl",
        "data warehouse",
        "data pipeline",
        "snowflake",
        "dbt",
        "databricks",
        "spark",
        "airflow",
        "redshift",
        "bigquery",
        "data engineer",
        "analytics engineer",
    ),
    "ml": (
        "machine learning",
        "deep learning",
        "model training",
        "pytorch",
        "tensorflow",
        "huggingface",
        "transformer",
        "llm ",
        " llm",
        "embedding",
        "fine-tuning",
        "fine tuning",
        "ml engineer",
        "ml platform",
    ),
    "platform": (
        "kubernetes",
        "k8s",
        "terraform",
        "ci/cd",
        "devops",
        "sre",
        "platform engineer",
        "infrastructure",
        "observability",
        "prometheus",
        "grafana",
        "ansible",
        "helm",
    ),
    "mobile": (
        "ios",
        "android",
        "swift",
        "swiftui",
        "kotlin",
        "jetpack compose",
        "react native",
        "flutter",
        "objective-c",
        "xcode",
    ),
}

# On a tie, prefer in this order. Fullstack wins when backend and frontend
# tie — that's almost always what the role actually is. Specialty roles
# (ml/data/platform/mobile) beat the generic backend/frontend buckets.
_PREFERENCE: tuple[Archetype, ...] = (
    "fullstack",
    "ml",
    "data",
    "platform",
    "mobile",
    "backend",
    "frontend",
)


def detect_archetype(jd_text: str) -> Archetype:
    """Pick the archetype with the highest signal count in ``jd_text``.

    Returns ``"generalist"`` when the JD has zero matches for any archetype.
    """
    text = jd_text.lower()
    scores: dict[Archetype, int] = {
        a: sum(text.count(s) for s in signals) for a, signals in _SIGNALS.items()
    }
    if not any(scores.values()):
        return "generalist"
    best = max(scores.values())
    winners = {a for a, s in scores.items() if s == best}
    # Strong fullstack signal: backend and frontend tied at the top with no
    # explicit "full stack" phrase. The role is almost always fullstack.
    if "backend" in winners and "frontend" in winners:
        return "fullstack"
    for archetype in _PREFERENCE:
        if archetype in winners:
            return archetype
    return "generalist"  # unreachable; mypy doesn't know that
