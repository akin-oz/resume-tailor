.PHONY: install dev api web test lint format format-check typecheck check previews

install:
	uv sync --all-extras

api:
	uv run uvicorn app.main:app --reload --app-dir api --port 8000

previews:
	uv run python scripts/build_previews.py

web:
	@echo "Frontend lands in a later slice."

dev: api

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
