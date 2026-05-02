"""POST /api/tailor — dispatches to OpenAI mode or stub mode.

* ``OPENAI_API_KEY`` set → ``tailor_ai`` runs the model with strict
  server-side validation. Hallucinated bullet IDs are dropped; profiles
  that violate the rules fall back to a clean ``profile_seed``
  truncation.
* No key → ``tailor_stub`` runs a deterministic, hermetic ranker. The
  output shape is identical, so the frontend has a single contract.

OpenAI transient errors (rate limit, connection, timeout) map to **503
problem+json** with a ``Retry-After`` header — never a generic 500.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError

from ..domain.models import Problem, TailorRequest, TailorResult
from ..domain.tailor import tailor_stub
from ..domain.tailor_ai import tailor_ai

router = APIRouter()

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI | None:
    """Lazily build the OpenAI client. ``None`` when no key is configured."""
    global _client
    if not os.getenv("OPENAI_API_KEY"):
        return None
    if _client is None:
        _client = AsyncOpenAI()
    return _client


def _problem(
    status: int,
    title: str,
    detail: str | None = None,
    *,
    retry_after: int | None = None,
) -> Response:
    body = Problem(status=status, title=title, detail=detail, retry_after=retry_after).model_dump(
        by_alias=True, exclude_none=True
    )
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
        headers=headers,
    )


def _translate_openai_error(exc: Exception) -> Response:
    """Map OpenAI transient errors to 503 problem+json with Retry-After."""
    if isinstance(exc, RateLimitError):
        return _problem(503, "AI rate limited", "OpenAI rate limit hit", retry_after=10)
    if isinstance(exc, APITimeoutError):
        return _problem(503, "AI timed out", "OpenAI request timed out", retry_after=5)
    if isinstance(exc, APIConnectionError):
        return _problem(503, "AI temporarily unavailable", str(exc), retry_after=5)
    raise exc


@router.post(
    "/tailor",
    response_model=TailorResult,
    response_model_by_alias=True,
)
async def tailor(req: TailorRequest) -> Any:
    client = _get_client()
    if client is None:
        return tailor_stub(req)
    try:
        return await tailor_ai(req, client=client)
    except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
        return _translate_openai_error(exc)
