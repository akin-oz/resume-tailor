"""POST /api/parse — multipart PDF upload → ParsedResume.

Pure-Python parser, no LLM. The output is a *starting point* for the
form on the frontend; the user reviews and edits before tailoring.
That confirmation step is what keeps the bullet-pool / no-hallucination
contract intact even though the parser uses heuristics.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse, Response

from ..domain.models import ParsedResume, Problem
from ..domain.parse import extract_pdf_text, parse_resume_lines

router = APIRouter()

PdfUpload = Annotated[UploadFile, File(...)]

_MAX_BYTES = 5 * 1024 * 1024  # 5 MB — typical resume is <500KB.
_MIN_TEXT_CHARS = 100


def _problem(status: int, title: str, detail: str | None = None) -> Response:
    body = Problem(status=status, title=title, detail=detail).model_dump(
        by_alias=True, exclude_none=True
    )
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


@router.post("/parse", response_model=ParsedResume, response_model_by_alias=True)
async def parse(file: PdfUpload) -> ParsedResume | Response:
    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        return _problem(415, "Only PDF supported", f"received content-type={file.content_type!r}")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_BYTES:
        return _problem(413, "File too large", f"max {_MAX_BYTES // 1024 // 1024} MB")
    if len(pdf_bytes) < 100 or not pdf_bytes.startswith(b"%PDF-"):
        return _problem(400, "Not a PDF", "file does not start with %PDF-")

    # Two-step: extract raw text first so we can detect a scanned PDF
    # against the *extraction* result, not against parsed-fields heuristics.
    # A real resume that just lacks a Summary section + bullet markers
    # would otherwise trigger a false "scanned PDF" rejection.
    try:
        lines = extract_pdf_text(pdf_bytes)
    except Exception as exc:  # pypdfium2 errors come through here
        return _problem(422, "Could not parse PDF", str(exc))

    if sum(len(line) for line in lines) < _MIN_TEXT_CHARS:
        return _problem(
            422,
            "Empty extraction",
            "Could not extract usable text — PDF may be scanned. Try a text-PDF.",
        )

    # Parser always succeeds — partial / empty output is fine; the form
    # surfaces ParseWarnings for the user to fill in manually.
    return parse_resume_lines(lines)
