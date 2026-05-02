from __future__ import annotations

from app.domain.models import (
    Contact,
    Experience,
    JobDescription,
    ResumeInput,
    TailoredExperience,
    TailorResult,
)
from app.domain.render import load_templates, project_for_render, render_html
from app.domain.tailor import tailor_stub
from app.main import app
from fastapi.testclient import TestClient

from .conftest import make_request, make_story

client = TestClient(app)


def _tailored(resume: ResumeInput, jd: JobDescription) -> TailorResult:
    return tailor_stub(make_request(resume, jd))


def test_load_templates_finds_all_three() -> None:
    templates = load_templates()
    assert {"modern", "classic", "compact"} <= set(templates)
    assert templates["modern"].name == "Modern"


def test_project_for_render_resolves_story_text(
    resume: ResumeInput, jd_backend: JobDescription
) -> None:
    tailored = _tailored(resume, jd_backend)
    rendered = project_for_render(resume, tailored)
    bullets = rendered["experiences"][0]["bullets"]
    # The tailor picked s1 first; its text must appear at index 0.
    assert "Designed payments API" in bullets[0]
    # Bullets are strings, not story objects.
    assert all(isinstance(b, str) for b in bullets)


def test_project_for_render_skips_unknown_experience_id(resume: ResumeInput) -> None:
    bogus = TailorResult(
        profile="A profile.",
        experiences=[TailoredExperience(experience_id="does-not-exist", story_ids=[])],
        skills=[],
        archetype_used="generalist",
    )
    rendered = project_for_render(resume, bogus)
    assert rendered["experiences"] == []


def test_render_html_contains_key_fields(resume: ResumeInput, jd_backend: JobDescription) -> None:
    tailored = _tailored(resume, jd_backend)
    html = render_html(resume, tailored, "modern")
    assert "<!DOCTYPE html>" in html
    assert resume.contact.name in html
    assert "Designed payments API" in html
    # No unresolved Jinja placeholders.
    assert "{{" not in html and "{%" not in html
    # Stylesheet is inlined.
    assert "<style>" in html and "@page" in html


def test_render_html_strict_undefined_works_on_minimal_resume() -> None:
    # A resume with no education and no skills should still render cleanly
    # — StrictUndefined would catch any context key the template forgets to gate.
    minimal = ResumeInput(
        contact=Contact(name="Min", email="min@example.com"),
        profile_seed="Engineer focused on shipping clean APIs and clear documentation.",
        experiences=[
            Experience(
                id="e1",
                company="Co",
                title="Engineer",
                start="2022",
                stories=[make_story("s1", "Built things.")],
            )
        ],
    )
    tailored = TailorResult(
        profile="A short profile.",
        experiences=[TailoredExperience(experience_id="e1", story_ids=["s1"])],
        skills=[],
        archetype_used="generalist",
    )
    html = render_html(minimal, tailored, "modern")
    assert "Built things." in html


def test_get_templates_route() -> None:
    r = client.get("/api/templates")
    assert r.status_code == 200
    body = r.json()
    assert any(t["id"] == "modern" for t in body)
    # camelCase wire format from the alias generator.
    assert "previewUrl" in body[0]


def test_post_render_html(resume: ResumeInput, jd_backend: JobDescription) -> None:
    tailored = _tailored(resume, jd_backend)
    payload = {
        "resume": resume.model_dump(by_alias=True, mode="json"),
        "tailored": tailored.model_dump(by_alias=True, mode="json"),
        "templateId": "modern",
        "format": "html",
    }
    r = client.post("/api/render", json=payload)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    assert "<!DOCTYPE html>" in r.text


def test_post_render_pdf(resume: ResumeInput, jd_backend: JobDescription) -> None:
    """End-to-end: POST /api/render with format=pdf returns real PDF bytes.

    No skip dance — WeasyPrint is a Python library, always available
    once deps are installed.
    """
    tailored = _tailored(resume, jd_backend)
    payload = {
        "resume": resume.model_dump(by_alias=True, mode="json"),
        "tailored": tailored.model_dump(by_alias=True, mode="json"),
        "templateId": "modern",
        "format": "pdf",
    }
    r = client.post("/api/render", json=payload)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    # PDF magic bytes and non-trivial body.
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 1000


def test_post_render_unknown_template_404(resume: ResumeInput, jd_backend: JobDescription) -> None:
    # "compact" is now registered, so test with a string that fails the
    # TemplateId Literal validation entirely.
    tailored = _tailored(resume, jd_backend)
    payload = {
        "resume": resume.model_dump(by_alias=True, mode="json"),
        "tailored": tailored.model_dump(by_alias=True, mode="json"),
        "templateId": "no-such-template",
        "format": "html",
    }
    r = client.post("/api/render", json=payload)
    assert r.status_code == 422  # Pydantic literal mismatch


def test_template_preview_404_when_missing() -> None:
    r = client.get("/api/templates/modern/preview")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
