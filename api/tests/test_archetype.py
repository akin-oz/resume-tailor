from __future__ import annotations

from app.domain.archetype import detect_archetype


def test_backend_signals_win() -> None:
    jd = "Senior backend engineer. Build REST APIs, microservices, and Postgres-backed services."
    assert detect_archetype(jd) == "backend"


def test_frontend_signals_win() -> None:
    jd = "React engineer wanted. Tailwind, responsive UI, browser performance."
    assert detect_archetype(jd) == "frontend"


def test_explicit_fullstack_phrase() -> None:
    jd = "Looking for a full stack engineer comfortable across the stack."
    assert detect_archetype(jd) == "fullstack"


def test_ml_outranks_backend() -> None:
    jd = (
        "ML engineer. Train transformer models in PyTorch. Some backend API "
        "work to expose inference."
    )
    assert detect_archetype(jd) == "ml"


def test_no_signals_returns_generalist() -> None:
    jd = "We are a small team looking for someone who cares about craft."
    assert detect_archetype(jd) == "generalist"


def test_backend_frontend_tie_prefers_fullstack() -> None:
    # Equal counts of "react" and "postgres" — fullstack wins by preference.
    jd = "react react postgres postgres"
    assert detect_archetype(jd) == "fullstack"


def test_cross_stack_signals_outweigh_backend_keywords() -> None:
    # Multiple cross-stack signals beat raw backend keyword count. A real
    # cross-stack JD usually clusters several such phrases — single-phrase
    # cross-stack hints aren't strong enough to override on their own
    # (deliberate; "across the stack" thrown into an otherwise backend
    # JD is just a flourish).
    jd = (
        "Senior engineer. React, Node.js, Postgres. Own features end to "
        "end. We want generalists happy to jump between frontend and "
        "backend."
    )
    assert detect_archetype(jd) == "fullstack"


def test_generalist_product_engineer_jd_is_fullstack() -> None:
    # Mirrors the Lette JD pattern in examples/: "Senior Product Engineer"
    # generalist role with TypeScript / React / Node / Postgres / AWS that
    # used to be misclassified as backend on raw keyword frequency.
    jd = (
        "Senior Product Engineer. Generalist mindset, happy to jump between "
        "frontend, backend, infra. TypeScript, React, Node.js, Prisma, "
        "PostgreSQL on AWS. Own features end to end."
    )
    assert detect_archetype(jd) == "fullstack"
