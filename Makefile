.PHONY: install dev api web test lint format typecheck check

install:
	uv sync --all-extras

api:
	uv run uvicorn app.main:app --reload --app-dir api --port 8000

web:
	@echo "Frontend lands in a later slice."

dev: api

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy

check: lint typecheck test
