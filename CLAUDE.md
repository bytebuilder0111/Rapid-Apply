# JD Analyzer — CLAUDE.md

Guidance for humans and AI assistants working in this repo. Keep the codebase simple and readable. Do not add infrastructure, abstractions, or libraries beyond `docs/SPEC.md`.

## Commands

Run from the repo root unless noted.

```bash
# API (FastAPI)
make api          # uvicorn app.main:app --reload --port 8000 (cwd backend/)
make migrate      # alembic upgrade head (cwd backend/)
make seed         # python -m app.seed (cwd backend/)
make lint-api     # ruff check + ruff format --check (cwd backend/)
make test-api     # pytest (cwd backend/)

# Web (Next.js)
make web          # pnpm dev (cwd frontend/)
make lint-web     # pnpm lint (cwd frontend/)
make test-web     # pnpm test (if/when tests exist)

# Both
make lint         # lint-api + lint-web
make test         # test-api (+ test-web when present)
```

Package managers:

- Backend: `uv` (`uv sync`, `uv run …`)
- Frontend: `pnpm` (`pnpm install`, `pnpm dev`, `pnpm build`)

Local stack: PostgreSQL via `DATABASE_URL`, API on `:8000`, web on `:3000`. Next.js rewrites `/api/*` to the backend.

## Folder layout

```
.
├── Makefile
├── CLAUDE.md
├── README.md
├── docs/
│   └── SPEC.md
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── .env.example
│   ├── tests/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── db.py
│       ├── deps.py
│       ├── errors.py
│       ├── permissions.py
│       ├── seed.py
│       ├── auth/
│       ├── users/
│       ├── profiles/
│       ├── analysis/
│       ├── ai/
│       ├── integrations/
│       └── sheets/
└── frontend/
    ├── package.json
    ├── .env.example
    ├── next.config.ts
    ├── middleware.ts
    ├── components.json
    ├── lib/
    │   ├── api.ts
    │   └── auth.ts
    ├── components/
    │   ├── ui/              # shadcn
    │   ├── layout/
    │   └── resume-selector/
    └── app/
        ├── login/
        ├── (admin)/
        ├── (client)/
        └── (bidder)/
```

Backend is grouped by feature. Each feature typically has `router.py`, `schemas.py`, `service.py`, and uses shared SQLAlchemy models (or a local `models.py` if the table is feature-owned).

## Conventions

### Backend

- Layering: **routers → services → models**. Routers handle HTTP only; never call OpenAI or Google from a router.
- Roles: enum in code. Permissions: a plain `dict[Role, set[str]]` in `app/permissions.py`. No permission tables.
- Scope every client/bidder query by `client_id`. Admin may query across clients.
- UUID primary keys; `created_at` / `updated_at` on mutable tables; index `(client_id, created_at)` for list queries.
- Soft-delete clients where the spec says so; deactivated users cannot log in.
- Errors: `{ "error": { "code": "...", "message": "..." } }`.
- Secrets at rest: Fernet (`ENCRYPTION_KEY`). Never return decrypted API keys or Google refresh tokens to the browser.
- AI: one entry point `app/ai/service.py`. Prompt + version string in one file under `app/ai/`.
- Sheets: one writer class under `app/sheets/`; background tasks via FastAPI `BackgroundTasks` only (no Celery/Redis).
- Rate-limit login and analyze (e.g. slowapi, in-process).
- Lint/format with Ruff; tests with pytest.

### Frontend

- Talk to the API only through `lib/api.ts` (typed fetch). No codegen.
- Auth: JWT access in memory/header flow as implemented with httpOnly refresh cookie; **no tokens in localStorage**.
- Middleware protects app routes; sidebar from `GET /api/v1/me` role.
- One shared Resume Selector for CLIENT and BIDDER.
- Forms: React Hook Form + Zod. Data: TanStack Query. UI: shadcn/ui + Tailwind. Light/dark mode.
- Generous timeouts and clear loading state for Analyze (5–20s).

### Process

1. Follow `docs/SPEC.md` build phases in order.
2. After each phase: lint + tests, fix failures, summarize, wait for **"continue"**.
3. Ask about ambiguities instead of guessing.
4. Do not add Docker, monorepo tooling, Redis, Celery, or extra libraries unless the spec asks for them.
