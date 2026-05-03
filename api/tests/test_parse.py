from __future__ import annotations

from app.domain.parse import (
    parse_contact,
    parse_education,
    parse_experience,
    parse_resume_lines,
    parse_skills,
    split_sections,
)
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


# --- Section splitting ----------------------------------------------------


def test_split_sections_groups_under_headers() -> None:
    lines = [
        "Ada Lovelace",
        "ada@example.com",
        "Summary",
        "Backend engineer with eight years of experience.",
        "Experience",
        "Senior Engineer",
        "Acme | 2021-Present",
        "Education",
        "BSc Computer Science, MIT",
    ]
    sections = split_sections(lines)
    assert sections["header"] == ["Ada Lovelace", "ada@example.com"]
    assert sections["summary"] == ["Backend engineer with eight years of experience."]
    assert sections["experience"][0] == "Senior Engineer"
    assert sections["education"] == ["BSc Computer Science, MIT"]


def test_split_sections_handles_no_headers() -> None:
    lines = ["Random text", "No structure"]
    sections = split_sections(lines)
    assert sections == {"header": ["Random text", "No structure"]}


# --- Contact parsing ------------------------------------------------------


def test_contact_extracts_name_email_phone() -> None:
    contact = parse_contact(["Ada Lovelace", "ada@example.com · +44 20 1234 5678 · London, UK"])
    assert contact.name == "Ada Lovelace"
    assert contact.email == "ada@example.com"
    assert contact.phone is not None and "1234 5678" in contact.phone
    assert contact.location == "London, UK"


def test_contact_extracts_linkedin_and_github() -> None:
    contact = parse_contact(
        [
            "Ada Lovelace",
            "linkedin.com/in/ada · github.com/ada · ada@example.com",
        ]
    )
    assert contact.linkedin == "https://linkedin.com/in/ada"
    assert contact.github == "https://github.com/ada"


def test_contact_skips_section_words_when_finding_name() -> None:
    contact = parse_contact(["ada@example.com"])
    assert contact.name == ""
    assert contact.email == "ada@example.com"


# --- Experience parsing ---------------------------------------------------


def test_experience_extracts_title_company_dates_bullets() -> None:
    lines = [
        "Senior Backend Engineer | Acme Payments",
        "Jan 2021 - Present",
        "• Designed payments API used by 12 internal services.",
        "• Mentored two engineers through promotion.",
    ]
    exps, warnings = parse_experience(lines)
    assert warnings == []
    assert len(exps) == 1
    e = exps[0]
    assert e.title == "Senior Backend Engineer"
    assert e.company == "Acme Payments"
    assert e.start.lower().startswith("jan 2021")
    assert e.end is None  # "Present"
    assert len(e.stories) == 2
    assert e.stories[0].text.startswith("Designed payments API")


def test_experience_handles_multiline_company() -> None:
    lines = [
        "Senior Engineer",
        "Acme",
        "2021 - 2023",
        "- Built things",
    ]
    exps, _ = parse_experience(lines)
    assert len(exps) == 1
    assert exps[0].title == "Senior Engineer"
    assert exps[0].company == "Acme"


def test_experience_splits_multiple_jobs_by_date_range() -> None:
    lines = [
        "Senior Engineer | Acme",
        "2021 - 2023",
        "• Did A",
        "• Did B",
        "Junior Engineer | Beta",
        "2019 - 2021",
        "• Did C",
    ]
    exps, _ = parse_experience(lines)
    assert len(exps) == 2
    assert exps[0].company == "Acme"
    assert exps[1].company == "Beta"
    assert len(exps[1].stories) == 1


def test_experience_warns_when_empty() -> None:
    _, warnings = parse_experience([])
    assert any(w.field == "experience" for w in warnings)


# --- Education parsing ----------------------------------------------------


def test_education_extracts_degree_and_school() -> None:
    edus, _ = parse_education(["BSc Computer Science — MIT", "2015 - 2019"])
    assert len(edus) == 1
    assert edus[0].degree == "BSc Computer Science"
    assert edus[0].school == "MIT"


# --- Skills parsing -------------------------------------------------------


def test_skills_splits_on_commas_and_pipes() -> None:
    assert parse_skills(["Python, FastAPI, PostgreSQL | Docker"]) == [
        "Python",
        "FastAPI",
        "PostgreSQL",
        "Docker",
    ]


def test_skills_dedupes_case_insensitively() -> None:
    assert parse_skills(["python, Python, PYTHON"]) == ["python"]


def test_skills_handles_bullets() -> None:
    assert parse_skills(["• Python", "• FastAPI"]) == ["Python", "FastAPI"]


# --- End-to-end on a synthetic resume -------------------------------------


_SAMPLE = """Ada Lovelace
ada@example.com · +44 20 1234 5678 · London, UK
linkedin.com/in/ada · github.com/ada

Summary
Backend engineer with eight years building payment platforms. Led teams of three to seven, owned services from design through production rollout.

Experience
Senior Backend Engineer | Acme Payments
Jan 2021 - Present
• Designed payments API used by 12 internal services.
• Mentored two engineers through promotion.
• Cut p99 latency 40% by rewriting the auth path.

Backend Engineer | Beta Inc
2018 - 2020
• Built billing service from scratch.
• Owned on-call rotation.

Education
BSc Computer Science — MIT
2014 - 2018

Skills
Python, FastAPI, PostgreSQL, Kubernetes, Docker
"""


def test_end_to_end_synthetic_resume() -> None:
    lines = [line.strip() for line in _SAMPLE.splitlines() if line.strip()]
    parsed = parse_resume_lines(lines)
    assert parsed.contact.name == "Ada Lovelace"
    assert parsed.contact.email == "ada@example.com"
    assert "linkedin.com/in/ada" in (parsed.contact.linkedin or "")
    assert "github.com/ada" in (parsed.contact.github or "")
    assert "Backend engineer" in parsed.profile_seed
    assert len(parsed.experiences) == 2
    assert parsed.experiences[0].company == "Acme Payments"
    assert parsed.experiences[1].company == "Beta Inc"
    assert len(parsed.experiences[0].stories) == 3
    assert "Python" in parsed.skills
    assert len(parsed.education) == 1
    # No critical warnings — this synthetic resume has everything.
    blockers = [w for w in parsed.warnings if w.field in {"contact.name", "contact.email"}]
    assert blockers == []


# --- Route -----------------------------------------------------------------


def test_parse_route_rejects_non_pdf() -> None:
    r = client.post(
        "/api/parse",
        files={"file": ("resume.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 415


def test_parse_route_rejects_bogus_pdf_bytes() -> None:
    # Non-PDF bytes (no %PDF- header) → 400.
    r = client.post(
        "/api/parse",
        files={"file": ("resume.pdf", b"not-actually-a-pdf-just-some-bytes", "application/pdf")},
    )
    assert r.status_code == 400


def test_parse_route_rejects_oversize() -> None:
    big = b"%PDF-1.4\n" + b"x" * (6 * 1024 * 1024)
    r = client.post(
        "/api/parse",
        files={"file": ("resume.pdf", big, "application/pdf")},
    )
    assert r.status_code == 413


# --- Real-world layout regression -----------------------------------------


# Verbatim lines from a real PDF that broke the parser before #PR-9:
# letter-spaced section headers (`PROF I LE`, `EX PERIENCE`, `TECHNICAL SKI L LS`)
# and unprefixed bullets (pypdfium2 dropped the • glyphs).
_LETTER_SPACED_RESUME = [
    "Akın Öztorun",
    "Frontend Engineer",
    "Türkiye • akin@akinoztorun.dev • linkedin.com/in/oztorun • +90 506 954 0174",
    "PROF I LE",
    "Senior Frontend Engineer with 9+ years of experience building TypeScript-first products.",
    "EX PERIENCE",
    "Senior Frontend Engineer (Freelance)",
    "Proxify",
    "Nov 2025 – Present",
    "Took over full frontend ownership of a Vue 3 / Nuxt platform for a German client.",
    "Led a Nuxt 4 migration to a Feature-Sliced architecture.",
    "Senior Software Engineer",
    "Proxify",
    "Jan 2022 – Oct 2025",
    "Owned ATS funnel handling ~400K applications per year.",
    "Increased completion from ~39% to ~65%.",
    "Frontend Engineer",
    "Skeyl",
    "Jun 2016 – Jan 2022",
    "Served as primary frontend owner for React/TypeScript SPAs.",
    "Raised Lighthouse scores from the 40s to the 90s.",
    "TECHNICAL SKI L LS",
    "TypeScript, React, Next.js, Vue 3, Nuxt, Pinia, Node.js, Tailwind CSS",
    "EDUCAT ION",
    "Bachelor's Degree, Metallurgical and Materials Engineering",
    "Karadeniz Technical University",
]


def test_letter_spaced_section_headers_are_detected() -> None:
    sections = split_sections(_LETTER_SPACED_RESUME)
    assert "summary" in sections, "PROF I LE should be detected as summary"
    assert "experience" in sections, "EX PERIENCE should be detected as experience"
    assert "skills" in sections, "TECHNICAL SKI L LS should be detected as skills"
    assert "education" in sections, "EDUCAT ION should be detected as education"


def test_real_resume_extracts_three_experiences_without_bullet_glyphs() -> None:
    """The parser must use date ranges as anchors when • glyphs are stripped."""
    parsed = parse_resume_lines(_LETTER_SPACED_RESUME)
    assert len(parsed.experiences) == 3
    titles = [e.title for e in parsed.experiences]
    companies = [e.company for e in parsed.experiences]
    assert "Senior Frontend Engineer (Freelance)" in titles
    assert "Senior Software Engineer" in titles
    assert "Frontend Engineer" in titles
    assert companies.count("Proxify") == 2
    assert "Skeyl" in companies
    # Each entry should have its bullets attached as stories, even though
    # the source had no • prefix on them.
    for exp in parsed.experiences:
        assert len(exp.stories) >= 1, f"{exp.title} has no stories"


def test_real_resume_extracts_skills() -> None:
    parsed = parse_resume_lines(_LETTER_SPACED_RESUME)
    assert "TypeScript" in parsed.skills
    assert "React" in parsed.skills
    assert "Tailwind CSS" in parsed.skills


# --- End-to-end via route -------------------------------------------------


def test_parse_route_returns_200_for_pdf_without_resume_structure() -> None:
    """Regression: a PDF with text but no recognizable section headers
    must return 200 with warnings, not a 422 'Empty extraction'.

    Real-world resumes commonly lack a Summary section and use
    layout (not bullet characters) for accomplishments. The old
    heuristic that summed `profile_seed + stories + skills` chars
    would falsely reject those. The check now operates on raw
    extracted text.
    """
    from weasyprint import HTML

    # 200+ chars of plain prose with no "Summary" / "Experience" /
    # "Skills" header — none of the parser's section parsers fire,
    # so profile_seed / stories / skills all end up empty.
    body = (
        "<p>This is the beginning of a long-winded document that has plenty "
        "of extractable text but does not follow any standard resume layout. "
        "It contains no recognized section headers, no bullet markers, and "
        "no date ranges. The parser will produce a ParsedResume with empty "
        "lists for experience, education, and skills, plus warnings noting "
        "what it could not detect.</p>"
    )
    pdf_bytes = HTML(string=f"<html><body>{body}</body></html>").write_pdf()
    r = client.post(
        "/api/parse",
        files={"file": ("plain.pdf", pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body_json = r.json()
    # Warnings should surface what's missing.
    warnings = body_json["warnings"]
    assert any(w["field"] == "experience" for w in warnings)
    assert any(w["field"] == "skills" for w in warnings)
