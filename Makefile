.PHONY: api web migrate seed lint lint-api lint-web test test-api test-web

api:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

web:
	cd frontend && pnpm dev

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m app.seed

lint-api:
	cd backend && uv run ruff check app tests && uv run ruff format --check app tests

lint-web:
	cd frontend && pnpm lint

lint: lint-api lint-web

test-api:
	cd backend && uv run pytest

test-web:
	cd frontend && pnpm test

test: test-api
