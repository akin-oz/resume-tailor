# syntax=docker/dockerfile:1.7
#
# Two-stage build:
#   1. builder — installs Python deps via uv into a venv. No chromium here.
#   2. runtime — copies the venv, installs Chromium and the system libs it
#      needs, drops privileges, and runs uvicorn.
#
# Final image is ~700MB (versus ~1.5GB for the official Microsoft Playwright
# Python image). Smaller image = faster cold start on Fly free tier.

# --- Builder ----------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# --no-install-project: just resolve deps. The project itself is plain Python
# under api/app/, run via PYTHONPATH at runtime.
RUN uv sync --frozen --no-dev --no-install-project


# --- Runtime ----------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

# System libraries Chromium needs at runtime. Mirrors what
# `playwright install --with-deps` would install — pinning here keeps the
# image deterministic and lets layer caching work.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libgbm1 libpango-1.0-0 libcairo2 libasound2 \
      fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    PYTHONPATH=/app/api \
    PYTHONUNBUFFERED=1

# Chromium binary into a shared path. Done as root so it's owned that way;
# we chown it to the app user before dropping privileges.
RUN mkdir -p /opt/ms-playwright && playwright install chromium

WORKDIR /app
COPY . .

RUN useradd -m -u 1000 app && chown -R app:app /app /opt/ms-playwright
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
