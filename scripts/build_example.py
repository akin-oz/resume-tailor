"""Regenerate the committed worked-example outputs in `examples/`.

Reads `examples/sample-resume.json` + `examples/sample-jd.txt`, runs the
stub-mode tailor, renders the modern template to PDF, and rasterizes a
2-up PNG preview so GitHub can render it inline.

Run after editing the sample inputs, the templates, or the tailor logic
itself, so the committed outputs stay an accurate snapshot::

    make eval-example
    # or:
    uv run python scripts/build_example.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.domain.models import (  # noqa: E402
    ResumeInput,
    TailorRequest,
)
from app.domain.render import render_html, render_pdf  # noqa: E402
from app.domain.tailor import tailor_stub  # noqa: E402

EXAMPLES = ROOT / "examples"
RESUME_PATH = EXAMPLES / "sample-resume.json"
JD_PATH = EXAMPLES / "sample-jd.txt"
TAILORED_PATH = EXAMPLES / "tailored.json"
PDF_PATH = EXAMPLES / "tailored.pdf"
PREVIEW_PATH = EXAMPLES / "tailored.preview.png"

# 2-up preview height in pixels — keeps the PNG small enough for GitHub
# to render inline without sacrificing readability of body copy.
PREVIEW_HEIGHT_PX = 1000


def _render_2up_png(pdf_bytes: bytes, target: Path) -> tuple[int, int]:
    """Rasterize all PDF pages side-by-side into one PNG."""
    import pypdfium2 as pdfium
    from PIL import Image

    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        # WeasyPrint emits A4 (595 pt wide); scale to PREVIEW_HEIGHT_PX wide pages.
        scale = PREVIEW_HEIGHT_PX / 595.0
        pages = [pdf[i].render(scale=scale).to_pil() for i in range(len(pdf))]
        gap_px = 24
        total_w = sum(p.width for p in pages) + gap_px * (len(pages) - 1)
        max_h = max(p.height for p in pages)
        out = Image.new("RGB", (total_w, max_h), (245, 245, 245))
        x = 0
        for p in pages:
            out.paste(p, (x, 0))
            x += p.width + gap_px
        out.save(target, format="PNG", optimize=True)
        return out.size
    finally:
        pdf.close()


def main() -> int:
    resume_data = json.loads(RESUME_PATH.read_text())
    jd_text = JD_PATH.read_text()

    req = TailorRequest.model_validate({"resume": resume_data, "jd": {"text": jd_text}})
    tailored = tailor_stub(req)

    TAILORED_PATH.write_text(tailored.model_dump_json(by_alias=True, indent=2) + "\n")
    print(f"wrote {TAILORED_PATH.relative_to(ROOT)}")

    resume = ResumeInput.model_validate(resume_data)
    html = render_html(resume, tailored, "modern")
    pdf_bytes = render_pdf(html)
    PDF_PATH.write_bytes(pdf_bytes)
    print(f"wrote {PDF_PATH.relative_to(ROOT)} ({len(pdf_bytes):,} bytes)")

    size = _render_2up_png(pdf_bytes, PREVIEW_PATH)
    print(f"wrote {PREVIEW_PATH.relative_to(ROOT)} ({size[0]}x{size[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
