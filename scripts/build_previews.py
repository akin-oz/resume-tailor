"""Generate templates/<id>/preview.png for every registered template.

Usage:
    uv run python scripts/build_previews.py

Renders the same fixture resume through each template (HTML → WeasyPrint
→ PDF), then rasterizes the first page via pypdfium2 to produce a
thumbnail PNG. Pure Python, no browser needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.domain.models import (  # noqa: E402
    Contact,
    Experience,
    JobDescription,
    ResumeInput,
    Story,
    TailorRequest,
    TailorSettings,
)
from app.domain.render import (  # noqa: E402
    TEMPLATES_DIR,
    load_templates,
    render_html,
    render_pdf,
)
from app.domain.tailor import tailor_stub  # noqa: E402

PREVIEW_WIDTH = 600
PREVIEW_HEIGHT = 800


def _fixture() -> tuple[ResumeInput, JobDescription]:
    """A representative resume + JD that exercises every template section."""
    resume = ResumeInput(
        contact=Contact(
            name="Ada Lovelace",
            email="ada@example.com",
            phone="+44 20 1234 5678",
            location="London, UK",
        ),
        profile_seed=(
            "Backend engineer with eight years building payment platforms. "
            "Led teams of three to seven, owned services from design through "
            "production rollout, and care a lot about clean APIs and observability."
        ),
        experiences=[
            Experience(
                id="exp1",
                company="Acme Payments",
                title="Senior Backend Engineer",
                location="London",
                start="2021-01",
                stories=[
                    Story(
                        id="s1",
                        text="Designed payments API used by 12 internal services.",
                        keywords=["api design", "ownership"],
                    ),
                    Story(
                        id="s2",
                        text="Mentored two engineers through promotion.",
                        keywords=["mentoring", "leadership"],
                    ),
                    Story(
                        id="s3",
                        text="Cut p99 latency 40% by rewriting the auth path.",
                        keywords=["performance"],
                    ),
                ],
            )
        ],
        skills=["Python", "PostgreSQL", "FastAPI", "Kubernetes"],
    )
    jd = JobDescription(
        text=(
            "Senior backend engineer to own a payments API. Mentor a small team, "
            "drive API design, ensure reliability via good observability. "
            "Python and PostgreSQL required; FastAPI a plus."
        )
    )
    return resume, jd


def _pdf_first_page_to_png(pdf_bytes: bytes, target: Path) -> None:
    """Rasterize the first page of a PDF into a PNG sized for thumbnail use."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page = pdf[0]
        # WeasyPrint outputs A4 at 72 DPI; PREVIEW_HEIGHT/A4_height is the scale.
        # A4 = 11.69 inches tall = 842 points. Aim for PREVIEW_HEIGHT pixels tall.
        scale = PREVIEW_HEIGHT / 842.0
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        # Crop/pad to PREVIEW_WIDTH so the thumbnail size is consistent.
        if image.width > PREVIEW_WIDTH:
            image = image.crop((0, 0, PREVIEW_WIDTH, image.height))
        image.save(target, format="PNG")
    finally:
        pdf.close()


def build() -> None:
    templates = load_templates()
    if not templates:
        print("No templates registered.", file=sys.stderr)
        return
    resume, jd = _fixture()
    tailored = tailor_stub(TailorRequest(resume=resume, jd=jd, settings=TailorSettings()))
    for tpl in templates.values():
        html = render_html(resume, tailored, tpl.id)
        pdf_bytes = render_pdf(html)
        target = TEMPLATES_DIR / tpl.id / "preview.png"
        _pdf_first_page_to_png(pdf_bytes, target)
        print(f"  wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
