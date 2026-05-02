"""Generate templates/<id>/preview.png for every registered template.

Usage:
    uv run python scripts/build_previews.py

Renders the same fixture resume through each template, screenshots the
result at thumbnail size, and writes the PNG into the template folder so
``GET /api/templates/<id>/preview`` serves it.

Run after editing a template's CSS or markup. CI runs this and commits
the result is a possible future workflow; for now, regenerate locally
when you change a template.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make the api package importable when running from the project root.
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
from app.domain.render import TEMPLATES_DIR, load_templates, render_html  # noqa: E402
from app.domain.tailor import tailor_stub  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

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


async def build() -> None:
    templates = load_templates()
    if not templates:
        print("No templates registered.", file=sys.stderr)
        return
    resume, jd = _fixture()
    tailored = tailor_stub(TailorRequest(resume=resume, jd=jd, settings=TailorSettings()))
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": PREVIEW_WIDTH, "height": PREVIEW_HEIGHT},
            device_scale_factor=2,
        )
        try:
            for tpl_id in templates:
                html = render_html(resume, tailored, tpl_id)
                page = await context.new_page()
                await page.set_content(html, wait_until="load")
                target = TEMPLATES_DIR / tpl_id / "preview.png"
                await page.screenshot(path=str(target), full_page=False)
                await page.close()
                print(f"  wrote {target.relative_to(ROOT)}")
        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(build())
