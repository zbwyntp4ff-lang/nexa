# NEXA Production Deployment

Primary provider for the team link: **Render Free** (Docker Web Service).  
Fallback (kept in repo): **Railway** — see [Railway fallback](#railway-fallback).

## Render Deployment

**Public URL:** _(set after first successful deploy, e.g. `https://nexa-xxxx.onrender.com`)_

| Field | Value |
|---|---|
| Provider | Render |
| Deployment | Docker Web Service (`runtime: docker`) |
| Blueprint | [`render.yaml`](render.yaml) |
| Image | [`Dockerfile`](Dockerfile) — Next.js + FastAPI + Caddy |
| Health | `GET /health` |
| Public port | Render `$PORT` (Caddy listens on `$PORT`) |

```text
Internet → Render HTTPS → Caddy :$PORT
                          ├─ /health, /api/* → uvicorn (internal)
                          └─ /*              → next start (internal)
```

Same-origin API: frontend builds with `NEXT_PUBLIC_API_BASE_URL=` (empty). Browser calls `/api/...` on the Render host. Local dev still defaults to `http://localhost:8420` when the env var is unset.

### Required environment variables

Set in Render Dashboard (never commit values):

| Variable | Notes |
|---|---|
| `OPENAI_API_KEY` | `<set in Render dashboard>` — required for real chat |
| `CORS_ALLOWED_ORIGINS` | `<set in Render dashboard>` — public HTTPS origin, e.g. `https://nexa-xxxx.onrender.com` |
| `BILLING_PUBLIC_BASE_URL` | `<set in Render dashboard>` — same public origin |
| `ENVIRONMENT` | `production` (Blueprint default) |
| `AI_PROVIDER` | `openai` (Blueprint default) |
| `OPENAI_MODEL` | `gpt-4o-mini` (Blueprint default) |
| `AUTH_SINGLE_USER` | `false` for team registration |
| `AUTH_COOKIE_SECURE` | `true` |
| `AUTH_COOKIE_SAMESITE` | `lax` |
| `AUTH_BOOTSTRAP_FIRST_OWNER` | `true` |
| `AUTH_SKIP_EMAIL_VERIFICATION` | `true` unless SMTP configured |
| `MEMORY_STORE_PATH` | `data/memory_store.json` |
| `AUTH_STORE_PATH` | `data/auth_store.json` |
| `BILLING_STORE_PATH` | `data/billing_store.json` |
| `AGENT_WORKSPACE_DIR` | `agent_workspace` |
| `LOG_LEVEL` | `INFO` |
| `WEB_SEARCH_PROVIDER` | `duckduckgo` |
| `REQUEST_TIMEOUT_SECONDS` | `90` |

Optional: `ANTHROPIC_API_KEY`, Stripe keys, SMTP — see [`.env.production.example`](.env.production.example).

There is **no** `DATABASE_URL` in this architecture: NEXA uses JSON file stores under `/app/data` (ephemeral on Render Free).

### Health

```bash
curl -fsS https://<public-url>/health
# {"status":"ok"}
```

Render health check path: `/health` (configured in `render.yaml`).

### Local development (unchanged)

```bash
# API
uvicorn app.main:app --reload --port 8420

# UI
cd frontend && npm run dev   # http://localhost:4820
```

### Deploy via Dashboard (recommended)

1. Push this repo to GitHub (do **not** commit `.env`).
2. Open [https://dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**.
3. Connect the GitHub repository; Render reads [`render.yaml`](render.yaml).
4. When prompted, set `OPENAI_API_KEY`, `CORS_ALLOWED_ORIGINS`, `BILLING_PUBLIC_BASE_URL`.
5. Deploy. Note the `*.onrender.com` URL.
6. Update `CORS_ALLOWED_ORIGINS` / `BILLING_PUBLIC_BASE_URL` to that exact HTTPS origin if not already set, then redeploy if needed.

### Deploy via CLI (after `render login`)

```bash
# Windows example path if installed under LocalAppData:
# %LOCALAPPDATA%\Programs\render\render.exe

render login
render blueprints validate render.yaml
# Then create/sync Blueprint from the Dashboard (GitHub-linked repo),
# or use Dashboard → New Web Service → Docker from the same repo.
```

### Logs

Render Dashboard → Service → **Logs**, or:

```bash
render logs -r <service-id>
```

### Redeploy

Push to the linked Git branch, or Dashboard → **Manual Deploy**.

### Rollback

Dashboard → **Events** / previous deploy → redeploy that commit.

### Team access

Existing NEXA auth (`/api/v1/auth`). First user can become owner (`AUTH_BOOTSTRAP_FIRST_OWNER=true`). Keep `AUTH_SINGLE_USER=false` so teammates can register. Do not share API keys — only the Render URL.

### Limitations (Render Free — honest)

- **Cold start / sleep:** free web services spin down after inactivity; first request can take tens of seconds.
- **RAM/CPU:** free plan is small (~512MB). Chromium + Next + Python may OOM.
- **Browser Runtime / Playwright:** may be `NOT_AVAILABLE` on Free if Chromium cannot launch; HTTP preview verification still runs. Never treat browser checks as PASS without a real Chromium launch.
- **Ephemeral filesystem:** `/app/data`, `agent_workspace`, build artifacts, uploads, videos are **lost on restart/redeploy**. Not durable production storage.
- **No guaranteed SLA** on Free.
- **Build time/size limits** may fail very large Docker builds; if so, trim Playwright or upgrade plan.

### AI

Production must use a real cloud provider (`AI_PROVIDER=openai` + `OPENAI_API_KEY`). If the key is missing, NEXA must return a normal provider/configuration error — not mock or fake success.

---

## Railway fallback

Kept in-repo: [`railway.toml`](railway.toml), same [`Dockerfile`](Dockerfile).

```bash
railway login
railway link   # or railway init
railway up
railway domain
```

Attach a Railway Volume at `/app/data` if you need persistence there. See earlier Railway sections in git history if needed; Render is the primary team URL path.
