"""FastAPI app entrypoint.

Intentionally thin. Cross-cutting concerns (rate limiting, structured
logging, X-Request-ID middleware) land alongside the features that
need them, not preemptively here.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ._browser import browser_lifespan, get_browser
from .domain.models import HealthStatus
from .routers import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with browser_lifespan():
        yield


app = FastAPI(title="Resume Tailor", version="0.1.0", lifespan=lifespan)

_cors_origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/healthz", response_model=HealthStatus, response_model_by_alias=True)
async def healthz() -> HealthStatus:
    # OpenAI wires up with the AI tailor slice.
    return HealthStatus(
        status="ok",
        playwright=(await get_browser()) is not None,
        openai=bool(os.getenv("OPENAI_API_KEY")),
    )
