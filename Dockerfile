# syntax=docker/dockerfile:1.7
#
# Two-stage build:
#   1. builder — installs Python deps via uv into a venv.
#   2. runtime — copies the venv, installs the native libs WeasyPrint
#      needs at runtime (Cairo, Pango, font support), drops privileges,
#      runs uvicorn.
#
# Final image: ~250MB. WeasyPrint replaces Playwright; no Chromium.

# --- Builder ----------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


# --- Runtime ----------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

# WeasyPrint native dependencies. Pinned package names matter — Debian
# bookworm ships specific versions.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libcairo2 \
      libpango-1.0-0 \
      libpangoft2-1.0-0 \
      libharfbuzz0b \
      libfontconfig1 \
      fonts-liberation \
      fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/api \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

ENV PORT=8080
EXPOSE 8080
# sh -c so $PORT is honored at runtime (Cloud Run sets it; local override
# via `docker run -e PORT=9000`). exec keeps uvicorn as PID 1 for clean
# signal handling on container shutdown.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
