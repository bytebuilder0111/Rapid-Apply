# JD Analyzer — Product Spec

You are a senior full-stack engineer building a web app called "JD Analyzer". Keep the codebase SIMPLE and readable. Do not add infrastructure, abstractions, or libraries beyond what this spec asks for.

## How to work

1. Read this whole spec first. Do NOT write code yet.
2. Save it to docs/SPEC.md and create CLAUDE.md at the repo root with the commands, folder layout, and conventions.
3. Give me an implementation plan: folder tree, database schema, API endpoint list, frontend route map. Then STOP and wait for my approval.
4. After approval, build phase by phase. After each phase, run lint + tests, fix failures, summarize, and wait for my "continue".
5. Ask me about anything ambiguous instead of guessing.

## Product

A user pastes a job description (JD). The app calls OpenAI to analyze it, identifies the MAIN backend skill (e.g. Python/Django, Node.js/NestJS, Java/Spring, Go, .NET, PHP/Laravel, Ruby/Rails), and recommends the best-matching resume profile. Saved analyses can be auto-recorded as a row in a Google Sheet configured per profile.

Roles: ADMIN, CLIENT, BIDDER.

## Stack (locked)

Two folders in one repo, no monorepo tooling, no Docker.

- `backend/` — Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async, asyncpg), Alembic, uv for packages, Ruff for lint/format, pytest for tests.
- `frontend/` — Next.js 15 (App Router), TypeScript strict, Tailwind CSS, shadcn/ui, TanStack Query, React Hook Form + Zod, pnpm.

Database: PostgreSQL (local install or a free Neon database; connection via `DATABASE_URL`).
AI: the official `openai` Python SDK, used only inside `backend/app/ai/`.
Google: `google-api-python-client` + `google-auth-oauthlib`.
No Redis, no Celery, no Docker, no message queue.

Running locally: `uvicorn` for the API, `pnpm dev` for the web app, a Makefile with `make api`, `make web`, `make migrate`, `make seed`.

## Keep it simple, but not sloppy

- Backend layering: routers (HTTP only) -> services (logic) -> SQLAlchemy models. Routers never call OpenAI or Google directly.
- Group backend code by feature: auth, users, profiles, analysis, ai, integrations, sheets.
- Roles are an enum; permissions are a simple dict in code mapping role -> allowed actions. No permission tables.
- Every query for client/bidder data is scoped by `client_id` so one client can never see another's data. Write tests for this.
- The AI call sits behind one function in `app/ai/service.py`, so swapping or adding a provider later touches one file.
- Sheet writing sits behind one class in `app/sheets/`, so adding Notion or Airtable later is a new class, not a rewrite.
- Frontend talks to the backend through one small typed fetch client in `lib/api.ts`. No code generation step.

## Auth

- Email + password, argon2 hashing.
- JWT access token (~15 min) plus refresh token in an httpOnly, Secure, SameSite=Lax cookie, rotated on use and stored hashed in the DB.
- Next.js rewrites `/api/*` to the backend so cookies are first-party.
- Next.js middleware protects routes; the sidebar is built from the role returned by `GET /api/v1/me`.
- Deactivated users cannot log in.
- Seed script creates the first ADMIN from `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## Roles and features

### ADMIN

- Dashboard: counts of clients, bidders, and analyses in the last 7 and 30 days.
- Clients: create, edit, deactivate/reactivate, reset password, soft delete.
- Bidders: create under a chosen client, assign exactly one of that client's profiles, edit, deactivate, reset password.
- View all profiles across clients (read, edit, delete).

### CLIENT (sidebar: Resume Selector, Config, Profiles, Integrations)

1. Resume Selector
   - Form: Company Name, Position Name, Job Description (large textarea), Job Link (URL, optional), Profile Select (the client's profiles, optional before analyzing).
   - "Analyze" calls the backend synchronously. The AI call may take 5 to 20 seconds, so set generous timeouts and show a clear loading state. Disable the button while it runs.
   - Result card: main backend skill and framework, secondary skills, seniority, key requirements, recommended profile with confidence and a short reason.
   - The profile dropdown pre-selects the AI's recommendation; the user can override it. "Save" stores the analysis and, if that profile has auto-record enabled, appends a Google Sheet row in a FastAPI background task.
   - History table: search, filter by profile and date, view the full result, open the job link, see record status, and a "Retry" button for failed sheet writes.
   - Non-blocking warning if the same job link or the same JD (matched by a normalized hash) was already analyzed by this client.

2. Config
   - For each profile: toggle "Auto Record to Google Sheet", enter the spreadsheet URL or ID (extract the ID automatically), pick the sheet tab (fetch the tab list from the backend), and a "Test" button that verifies write access.

3. Profiles
   - CRUD for resume profiles. The full profile spec comes later; for now use a placeholder model: `id`, `client_id`, `name`, `primary_backend_skill`, `skills` (text[]), `notes`, `is_active`, `created_at`, `updated_at`.
   - Keep profile fields contained (model, schema, form, and the AI context builder) so adding fields later is a small change.

4. Integrations
   - OpenAI API key: save encrypted, display masked (`sk-...abcd`), "Test key", delete. Model name selectable, defaulting to `DEFAULT_AI_MODEL`.
   - Google account: "Connect Google" OAuth handled by the backend (authorize URL -> Google -> backend callback -> redirect back to the frontend). Scopes: `openid`, `email`, `https://www.googleapis.com/auth/spreadsheets`, with offline access so a refresh token is stored. Show the connected email, plus "Disconnect".
   - If a token refresh fails, mark the connection `NEEDS_RECONNECT` and show a banner to the client and its bidders.

### BIDDER (sidebar: Resume Selector, Config)

- Belongs to one client and is assigned exactly one profile. Uses the client's OpenAI key and Google connection.

1. Resume Selector: the same component as the client, with the profile dropdown limited to the assigned profile. A bidder sees only their own analyses; the owning client sees all of them.
2. Config: Google Sheet auto-record for the assigned profile only. This setting is personal to the bidder and, when enabled, is used instead of the client's profile-level sheet for that bidder's analyses.

## AI analysis

- Build the prompt from the JD plus a compact list of the client's active profiles (`id`, `name`, `primary_backend_skill`, `skills`).
- Use OpenAI structured output (JSON schema) and validate with this Pydantic model:
  - `main_backend_skill`: str
  - `backend_framework`: str | None
  - `secondary_skills`: list[str]
  - `seniority`: `"junior"` | `"mid"` | `"senior"` | `"lead"` | `"unknown"`
  - `key_requirements`: list[str]
  - `recommended_profile_id`: str | None
  - `confidence`: float (0 to 1)
  - `reasoning`: str (max 3 sentences)
- Keep the prompt in one file with a version string; store the prompt version and model on each analysis.
- On invalid JSON or an unknown profile id, retry once, then return a readable error.
- Map these failures to clear user-facing messages: no API key set, invalid key, rate limit, timeout, provider error.
- Store per-call token usage and latency on the analysis row (no separate logging system).

## Google Sheet recording

- Columns: Date, Company, Position, Job Link, Main Backend Skill, Framework, Secondary Skills, Seniority, Profile Used, Recorded By, Confidence.
- Write the header row first if the tab is empty.
- Track `record_status` (`PENDING` / `SUCCESS` / `FAILED` / `SKIPPED`), attempts, and `last_error` on the analysis. Never write the same analysis to the same sheet twice.
- A sheet failure never blocks saving the analysis. "Retry" re-runs just the sheet write.

## Data model (minimum)

- `users` (id, email, password_hash, name, role, is_active, client_id nullable, assigned_profile_id nullable, timestamps)
- `refresh_tokens` (hashed token, user, expiry, revoked)
- `profiles` (placeholder fields above)
- `ai_settings` (client_id unique, provider, model, api_key_encrypted)
- `google_connections` (client_id unique, email, refresh_token_encrypted, status)
- `sheet_configs` (client_id, profile_id, user_id nullable for a bidder's personal setting, enabled, spreadsheet_id, sheet_name)
- `analyses` (id, client_id, created_by, company_name, position_name, job_description, jd_hash, job_link, recommended_profile_id, selected_profile_id, result JSONB, model, prompt_version, tokens, latency_ms, record_status, record_attempts, record_error, created_at)

Use UUID primary keys, `created_at`/`updated_at` everywhere, and index `(client_id, created_at)` for list queries.

## Security

- Encrypt the OpenAI key and Google refresh token at rest with Fernet from `cryptography`, keyed by `ENCRYPTION_KEY`. Never send decrypted secrets to the browser.
- Rate-limit login and analyze endpoints (a simple in-process limiter like slowapi is fine).
- No tokens in localStorage.
- Consistent error shape: `{ "error": { "code": ..., "message": ... } }`.

## Frontend

- Responsive dashboard: sidebar, top bar with user menu, light/dark mode.
- One shared Resume Selector component used by both client and bidder.
- Loading skeletons, empty states, toasts, confirm dialogs on destructive actions, inline form validation.

## Environment

Provide `backend/.env.example` and `frontend/.env.example` covering: `DATABASE_URL`, `JWT_SECRET`, `ENCRYPTION_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DEFAULT_AI_MODEL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `FRONTEND_URL`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL`.

## Build phases

1. Repo setup: both apps running, Makefile, Ruff, TypeScript config, health endpoint, CLAUDE.md.
2. Models + Alembic migrations, auth (login, refresh, logout, /me), role checks, client_id scoping, admin seed.
3. Frontend shell: login page, layouts, role-based sidebar, API client.
4. Admin: client and bidder management, profile assignment, dashboard.
5. Profiles CRUD and Integrations (encrypted OpenAI key, test key).
6. Analysis: AI service, Resume Selector UI, result card, save, history, duplicate warning.
7. Google OAuth, sheet configs (client per-profile and bidder personal), sheet writing in a background task, Config UI, retry, reconnect banner.
8. Finish: tests for role permissions and client_id isolation, README with setup steps, Google Cloud OAuth setup instructions (consent screen, test users, redirect URI), and a deployment guide for Vercel (frontend) + Railway or Render (backend) + Neon (database).
