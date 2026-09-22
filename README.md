# JD Analyzer

Monorepo-style workspace (no monorepo tooling): FastAPI backend + Next.js frontend.

See `docs/SPEC.md` for the product spec and `CLAUDE.md` for commands and conventions.

## Quick start (Phase 1+)

```bash
# Backend
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Frontend (another terminal)
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

Or from the repo root: `make api` / `make web`.

Health check: http://localhost:8000/health
