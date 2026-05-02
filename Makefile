.PHONY: install install-web dev api web test lint format format-check typecheck check previews build-web deploy-web

install:
	uv sync --all-extras
	cd web && npm install

install-web:
	cd web && npm install

api:
	uv run uvicorn app.main:app --reload --app-dir api --port 8000

previews:
	uv run python scripts/build_previews.py

web:
	cd web && npm run dev

# Runs both servers in parallel. Stop with Ctrl-C; make kills both.
dev:
	$(MAKE) -j 2 api web

# Production build of the frontend. Set VITE_API_BASE to point at the
# deployed backend so the bundle hardcodes the right URL.
build-web:
	cd web && npm run build

# Deploy frontend to Cloudflare Workers Static Assets. Requires
# CLOUDFLARE_API_TOKEN in the environment (or `wrangler login` first).
deploy-web: build-web
	cd web && npx wrangler deploy

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy

check: lint format-check typecheck test
