"""FastAPI app entrypoint.

Intentionally thin. Cross-cutting concerns (rate limiting, structured
logging, X-Request-ID middleware) land alongside the features that
need them, not preemptively here.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .domain.models import HealthStatus
from .routers import api_router

app = FastAPI(title="Resume Tailor", version="0.1.0")

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


@app.get("/healthz", response_model=HealthStatus)
def healthz() -> HealthStatus:
    # Playwright wires up with the render slice; OpenAI with the AI tailor slice.
    return HealthStatus(
        status="ok",
        playwright=False,
        openai=bool(os.getenv("OPENAI_API_KEY")),
    )
