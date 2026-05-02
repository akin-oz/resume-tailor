"""Render routes: GET /api/templates and POST /api/render.

PDF rendering requires a Playwright Chromium binary. When the browser
isn't available, the route returns 503 problem+json with a clear hint
rather than 500 — the user can still get HTML output.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from playwright.async_api import Browser

from .._browser import get_browser
from ..domain.models import Problem, RenderRequest, TemplateMeta
from ..domain.render import TEMPLATES_DIR, load_templates, render_html, render_pdf

router = APIRouter()

BrowserDep = Annotated[Browser | None, Depends(get_browser)]

# Loaded once at import; restart the app to pick up new template folders.
_TEMPLATES: dict[str, TemplateMeta] = load_templates()


def _problem(status: int, title: str, detail: str | None = None) -> Response:
    body = Problem(status=status, title=title, detail=detail).model_dump(
        by_alias=True, exclude_none=True
    )
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


@router.get(
    "/templates",
    response_model=list[TemplateMeta],
    response_model_by_alias=True,
)
def list_templates() -> list[TemplateMeta]:
    return list(_TEMPLATES.values())


@router.get("/templates/{template_id}/preview")
def template_preview(template_id: str) -> Response:
    preview = TEMPLATES_DIR / template_id / "preview.png"
    if not preview.is_file():
        return _problem(
            404, "Preview not generated", f"templates/{template_id}/preview.png missing"
        )
    return FileResponse(preview, media_type="image/png")


@router.post("/render")
async def render(req: RenderRequest, browser: BrowserDep) -> Response:
    if req.template_id not in _TEMPLATES:
        return _problem(
            404, "Unknown template", f"no template registered with id={req.template_id}"
        )
    html = render_html(req.resume, req.tailored, req.template_id)
    if req.format == "html":
        return HTMLResponse(content=html)
    if browser is None:
        return _problem(
            503,
            "PDF rendering unavailable",
            "Chromium isn't installed. Run `make install-browsers` (or "
            "`uv run playwright install chromium`) and restart the server.",
        )
    pdf_bytes = await render_pdf(browser, html)
    return Response(content=pdf_bytes, media_type="application/pdf")
