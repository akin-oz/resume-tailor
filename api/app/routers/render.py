"""Render routes: GET /api/templates and POST /api/render.

PDF generation uses WeasyPrint — pure Python, no headless browser. The
route is sync; FastAPI runs sync handlers in a threadpool.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from ..domain.models import Problem, RenderRequest, TemplateMeta
from ..domain.render import TEMPLATES_DIR, load_templates, render_html, render_pdf

router = APIRouter()

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
def render(req: RenderRequest) -> Response:
    if req.template_id not in _TEMPLATES:
        return _problem(
            404, "Unknown template", f"no template registered with id={req.template_id}"
        )
    html = render_html(req.resume, req.tailored, req.template_id)
    if req.format == "html":
        return HTMLResponse(content=html)
    pdf_bytes = render_pdf(html)
    return Response(content=pdf_bytes, media_type="application/pdf")
