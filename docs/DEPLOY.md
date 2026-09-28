# Deploying (Render + Vercel + Neon, free tiers)

```
Browser ──► Vercel (Next.js) ──/api/* rewrite──► Render (FastAPI) ──► Neon (Postgres)
                                                     └──► OpenAI, Google Sheets
```

The browser only talks to the Vercel site. `/api/*` is forwarded to Render by
`frontend/next.config.ts`, so the login cookie stays first-party and no CORS setup is needed.

Do the steps in order: Render first (you need its URL for Vercel), then Vercel (you need its
URL for Render and Google).

## 1. Database (Neon)

You can keep using the current Neon database: it already has the clients, profiles, resume
summaries, sheet settings and imported history. Migrations run automatically when the API
starts.

After deploying, point your **local** `backend/.env` at a separate Neon branch (Neon console →
Branches → Create branch), so local testing doesn't touch live data.

Use the `postgresql+asyncpg://…` form of the connection string, as in `backend/.env`.

## 2. Backend on Render

1. <https://dashboard.render.com> → **New** → **Blueprint** → connect GitHub and pick the
   `Rapid-Apply` repository. Render reads `render.yaml` and creates `jd-analyzer-api`.
2. It asks for the values marked `sync: false`:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | same as `backend/.env` |
   | `ENCRYPTION_KEY` | **same as `backend/.env`**: the saved OpenAI key and Google login are encrypted with it; a new key makes them unreadable |
   | `JWT_SECRET` | a new random value: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `ADMIN_PASSWORD` | anything; only used by `app.seed` if no admin exists yet |
   | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | same as `backend/.env` |
   | `GOOGLE_REDIRECT_URI` | `https://<render-name>.onrender.com/api/v1/integrations/google/callback` |
   | `FRONTEND_URL`, `CORS_ORIGINS` | your Vercel URL, e.g. `https://jd-analyzer.vercel.app` (fill in a placeholder now and fix it after step 3) |

3. Deploy. When it's live, <https://your-render-name.onrender.com/health> returns
   `{"status":"ok"}`.

With `FRONTEND_URL` on https, the API refuses to start if `JWT_SECRET` is a placeholder or
`ENCRYPTION_KEY` is missing. The Render logs then show exactly what to fix.

## 3. Frontend on Vercel

1. <https://vercel.com/new> → import the `Rapid-Apply` repository.
2. **Root Directory:** `frontend`. The framework (Next.js) and pnpm are detected automatically.
3. **Environment variable:** `BACKEND_URL` = `https://<render-name>.onrender.com` (no trailing
   slash).
4. Deploy, then copy the site URL.

## 4. Connect the pieces

1. Render → `jd-analyzer-api` → Environment: set `FRONTEND_URL` and `CORS_ORIGINS` to the
   Vercel URL. Render redeploys.
2. Google Cloud Console → **Google Auth Platform → Clients** → your OAuth client:
   - **Authorized redirect URIs:** add
     `https://<render-name>.onrender.com/api/v1/integrations/google/callback`
     (keep the localhost one for local development).
3. Sign in at the Vercel URL as **Max**. Integrations should show Google as connected (the
   connection is stored in the database). If it asks to reconnect, click **Connect Google**
   once.

## 5. Keep the API awake (optional, recommended)

Render's free service sleeps after ~15 minutes idle, and the next request then waits 30–60
seconds. To avoid that, create a free job at <https://cron-job.org> that calls
`https://<render-name>.onrender.com/health` every 10 minutes. One always-on service fits in
Render's 750 free hours a month.

## Updating

Push to `main`: Render and Vercel both redeploy automatically, and new migrations run when
the API restarts.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Login page says the API server didn't respond | `BACKEND_URL` on Vercel is wrong, or the Render service is asleep or failed (check Render logs) |
| Google: `redirect_uri_mismatch` | `GOOGLE_REDIRECT_URI` on Render doesn't exactly match the URI in Google Cloud |
| After Google sign-in you land on localhost | `FRONTEND_URL` on Render still points at localhost |
| OpenAI key shows as saved but analyses fail to decrypt it | `ENCRYPTION_KEY` on Render differs from the one used when the key was saved |
