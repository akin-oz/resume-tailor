"""POST /api/tailor — thin HTTP layer over ``domain.tailor.tailor_stub``.

When AI mode lands, this dispatches to the OpenAI implementation if a key
is configured and falls back to the stub otherwise. For now it always
runs the stub so the frontend works without any external dependency.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..domain.models import TailorRequest, TailorResult
from ..domain.tailor import tailor_stub

router = APIRouter()


@router.post(
    "/tailor",
    response_model=TailorResult,
    response_model_by_alias=True,
)
def tailor(req: TailorRequest) -> TailorResult:
    return tailor_stub(req)
