"""HTML + PDF rendering: Jinja2 + folder-based template registration.

Each template lives in its own folder under ``templates/<id>/`` with three
files: ``template.html.j2``, ``style.css``, and ``meta.json``. Adding a
template requires zero backend code changes — drop a folder, restart the
app, it shows up in ``GET /api/templates``.

Templates see a denormalized "renderable" dict: stories already filtered
and ordered per the tailor's selection, so the templates themselves stay
dumb (no ID joins, no sorting, no validation logic).

PDF generation goes through WeasyPrint — a Python library, no headless
browser. Resumes are static paged content (no JS, simple CSS), exactly
WeasyPrint's sweet spot. Drops Docker image size by ~450MB and removes
the browser-singleton lifespan dance entirely.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from weasyprint import HTML

from .models import ResumeInput, TailorResult, TemplateId, TemplateMeta

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"

_REQUIRED_FILES = ("template.html.j2", "style.css", "meta.json")


def load_templates() -> dict[str, TemplateMeta]:
    """Scan ``templates/`` for valid template folders.

    Folders missing any required file are skipped silently. ``meta.json``
    is parsed via ``TemplateMeta`` so a malformed manifest fails loudly at
    startup rather than at first request.
    """
    out: dict[str, TemplateMeta] = {}
    if not TEMPLATES_DIR.is_dir():
        return out
    for entry in sorted(TEMPLATES_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "_")):
            continue
        if not all((entry / f).is_file() for f in _REQUIRED_FILES):
            continue
        meta = TemplateMeta.model_validate_json((entry / "meta.json").read_text())
        # render_html() resolves by folder name, so meta.id must match.
        if meta.id != entry.name:
            raise ValueError(f"Template id {meta.id!r} does not match folder name {entry.name!r}")
        if meta.id in out:
            raise ValueError(f"Duplicate template id: {meta.id}")
        out[meta.id] = meta
    return out


def project_for_render(resume: ResumeInput, tailored: TailorResult) -> dict[str, Any]:
    """Join ResumeInput + TailorResult into the shape templates consume.

    Stories are resolved to their text in the order chosen by the tailor.
    Unknown IDs are skipped defensively — the tailor pipeline already drops
    them, but a template should never crash on a malformed projection.
    """
    by_exp_id = {exp.id: exp for exp in resume.experiences}
    rendered_exps: list[dict[str, Any]] = []
    for te in tailored.experiences:
        exp = by_exp_id.get(te.experience_id)
        if exp is None:
            continue
        story_by_id = {s.id: s.text for s in exp.stories}
        bullets = [story_by_id[sid] for sid in te.story_ids if sid in story_by_id]
        rendered_exps.append(
            {
                "company": exp.company,
                "title": exp.title,
                "location": exp.location,
                "start": exp.start,
                "end": exp.end,
                "bullets": bullets,
            }
        )
    return {
        "contact": resume.contact,
        "profile": tailored.profile,
        "experiences": rendered_exps,
        "education": resume.education,
        "skills": tailored.skills,
    }


def render_html(resume: ResumeInput, tailored: TailorResult, template_id: TemplateId) -> str:
    """Render the resume to a complete, self-contained HTML document.

    ``StrictUndefined`` makes missing context keys raise during rendering
    rather than silently producing empty markup — caught in tests, not
    discovered in a generated PDF.
    """
    template_dir = TEMPLATES_DIR / template_id
    if not template_dir.is_dir():
        raise FileNotFoundError(f"Unknown template: {template_id}")
    env = Environment(
        loader=FileSystemLoader(template_dir),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("template.html.j2")
    stylesheet = (template_dir / "style.css").read_text()
    return template.render(
        **project_for_render(resume, tailored),
        stylesheet=stylesheet,
    )


def render_pdf(html: str) -> bytes:
    """Render a self-contained HTML document to A4 PDF bytes.

    The HTML must inline all assets (no external resources) — that's why
    ``render_html`` inlines the stylesheet. WeasyPrint honors the
    ``@page`` size declared in the template's CSS.

    Synchronous: WeasyPrint is fast enough (~200-500ms per resume) and
    has no async API. FastAPI runs sync handlers in a threadpool.
    """
    return HTML(string=html).write_pdf()  # type: ignore[no-any-return]
