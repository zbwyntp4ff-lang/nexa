# NEXA Production Deployment

**NEXA 2.0 (cloud-first):** the public product path is a multi-user HTTPS
backend + frontend with cloud AI providers (keys server-side only), auth,
per-user isolation, and durable storage (`DATABASE_URL` + volume or managed
Postgres). **Desktop + Ollama remain optional** for personal/local use.

**Not public yet:** do not deploy production or buy paid cloud resources until
the owner explicitly confirms. This doc prepares the path; it is not a launch claim.

**NEXA 1.0 Desktop** (Windows installer, local data, Ollama) remains supported.

This document prepares NEXA for a **future** public HTTPS URL. Nothing here
purchases domains, creates paid cloud resources, or claims the app is already
published.

**Open-beta staging (persistent disk + SMTP + named model):** see
[`docs/STAGING_DEPLOYMENT.md`](docs/STAGING_DEPLOYMENT.md) and
[`deploy/render-staging.example.yaml`](deploy/render-staging.example.yaml).  
Root [`render.yaml`](render.yaml) Free/ephemeral smoke is **not** that profile.

Primary free cloud path: **Render Free** (Docker Web Service) — ephemeral only.  
Fallback: **Railway** (needs a volume for durable login). For durable first-user
hosting prefer Desktop, or a **Linux VPS** with a volume — see [Linux VPS](#linux-vps).

## Local vs public (facts from this repo)

| Piece | How it runs today | Ports |
|---|---|---|
| Backend | `uvicorn app.main:app` | **8420** (local) |
| Frontend (dev) | `cd frontend && npm run dev` | **4820** |
| Frontend (prod in Docker) | `next start` behind Caddy | internal **3000** |
| Public edge (Docker) | Caddy in [`deploy/Caddyfile`](deploy/Caddyfile) | **`$PORT` / 8080** |
| Desktop | Electron + optional local API | UI **48420**, API **8420** |

Data layers:

| Store | Backend | Notes |
|---|---|---|
| Auth, memory, tokens, billing, plugins, knowledge, profiles | JSON under `data/` | Need a **persistent volume** (or accept ephemeral Free tier) |
| Conversations (server history) | **`DATABASE_URL`** SQLite or Postgres | Migrates on startup (`CREATE TABLE IF NOT EXISTS`) |
| Attachments / videos | local dirs | Prefer volume |

Env profiles: [`.env.development.example`](.env.development.example),
[`.env.testing.example`](.env.testing.example),
[`.env.production.example`](.env.production.example),
[`.env.render-free.example`](.env.render-free.example).

Durable public checklist: [`docs/STORAGE_MATRIX.md`](docs/STORAGE_MATRIX.md),
[`docs/EDGE_RATE_LIMITING.md`](docs/EDGE_RATE_LIMITING.md),
[`deploy/render-durable.example.yaml`](deploy/render-durable.example.yaml),
[`deploy/railway.env.example`](deploy/railway.env.example).
`TOKENS_ENFORCE=true` is required on every internet-facing service; durable
`NEXA_STORAGE_MODE=persistent` refuses unsafe startup settings.

AI: `AI_PROVIDER=mock|openai|anthropic|gemini|openrouter|ollama|local`.
**Ollama on a laptop is not reachable from a remote VPS.** Public deploy must
use a cloud provider with keys **only** in the host environment (never in the
browser). Set `allow_cloud_on_documents` / Learning settings before sending
KB text to cloud models.

---

## Render Free Test (prepared — not published until you confirm)

Use this path for a **free smoke / invite-only test**. It is **not** durable production.

| Constraint | Impact |
|---|---|
| No persistent disk | Auth, sessions, memory, tokens, uploads under `/app/data` are **ephemeral** |
| Sleep after idle | Cold start can take tens of seconds |
| ~512MB RAM | Playwright/Chromium may fail; chat UI + API still the target |
| No custom domain / Stripe in this mode | Use `*.onrender.com` only; leave Stripe unset |
| Ollama on your PC | **Not** reachable from Render — use `AI_PROVIDER=mock` or cloud OpenAI |

**Safe defaults in [`render.yaml`](render.yaml):** `AI_PROVIDER=mock`, auth **enabled** (`TOKENS_ENFORCE=true`), email verification skipped only because SMTP is usually absent on free test (`EMAIL_PROVIDER=console`), Stripe unset, `NEXA_STORAGE_MODE=ephemeral`.

**Do not** store important accounts only on Free. Prefer Railway+volume or a VPS when data must survive restarts.

Dashboard checklist (after you explicitly approve deploy):

1. Push this repo to GitHub (**never** commit `.env`).
2. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint** → select repo (`render.yaml`).
3. Plan: **Free**. Do not add paid disk / custom domain / Stripe.
4. Set secrets in Dashboard only if needed: optional `OPENAI_API_KEY` (and switch `AI_PROVIDER` to `openai`), optional `AUTH_OWNER_EMAILS`.
5. Deploy. Copy the `https://….onrender.com` URL.
6. Set `CORS_ALLOWED_ORIGINS`, `AUTH_PUBLIC_BASE_URL`, `BILLING_PUBLIC_BASE_URL` to that **exact** origin → **Manual Deploy** / restart.
7. Check `GET https://….onrender.com/health` → `{"status":"ok"}`.
8. Register one test user; expect **data loss** after sleep/redeploy.

Template: [`.env.render-free.example`](.env.render-free.example).

---

## Render Deployment

**Public URL:** _(not set until a deploy is approved and succeeds, e.g. `https://nexa-xxxx.onrender.com`)_

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
| `AUTH_BOOTSTRAP_FIRST_OWNER` | `false` + set `AUTH_OWNER_EMAILS` (or `true` only for a controlled first bootstrap) |
| `AUTH_SKIP_EMAIL_VERIFICATION` | `false` when SMTP is real; otherwise signup cannot complete |
| `AUTH_PUBLIC_BASE_URL` | same public HTTPS origin (OAuth / device links) |
| `MEMORY_STORE_PATH` | `data/memory_store.json` |
| `AUTH_STORE_PATH` | `data/auth_store.json` |
| `TOKEN_STORE_PATH` | `data/token_store.json` |
| `BILLING_STORE_PATH` | `data/billing_store.json` |
| `AGENT_WORKSPACE_DIR` | `agent_workspace` |
| `LOG_LEVEL` | `INFO` |
| `WEB_SEARCH_PROVIDER` | `duckduckgo` |
| `REQUEST_TIMEOUT_SECONDS` | `90` |
| SMTP (`EMAIL_PROVIDER=smtp`, host/user/pass/`EMAIL_FROM`) | required if email verification is enabled |

Optional: `ANTHROPIC_API_KEY`, Stripe keys — see [`.env.production.example`](.env.production.example).

**Storage (cloud-first):** set `DATABASE_URL` (SQLite on a volume or managed
Postgres) for conversations + SQL memory. Auth, tokens, profiles, plugins, and
knowledge still use JSON under `/app/data` and **require a persistent volume**
for durable accounts. On Render Free (`NEXA_STORAGE_MODE=ephemeral`) all of
`/app/data` is lost on sleep/restart — not a public durable release.

For a public durable launch set `ENVIRONMENT=production`,
`NEXA_STORAGE_MODE=persistent`, and the values in [`.env.production.example`](.env.production.example).
Startup then refuses unsafe combinations (skipped email verification, mock AI,
insecure cookies, missing CORS / `AUTH_PUBLIC_BASE_URL`).

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

**Required for durable login:** attach a Railway Volume at `/app/data`. Without it,
`auth_store.json` (accounts + sessions) is wiped on every restart — users appear
“logged out after a few hours.” Session TTL is 90 days with sliding renewal on
activity; logout still revokes immediately.

```bash
railway volume add -m /app/data
railway variable set AUTH_SESSION_TTL_SECONDS=7776000 AUTH_COOKIE_SECURE=true
```

See earlier Railway sections in git history if needed; Render Free remains ephemeral unless a disk is attached.

---

## Linux VPS

Suitable when you need a durable public HTTPS URL without relying on free-tier
ephemeral disks. Do **not** buy a VPS or domain until the owner confirms.

### Suggested sizing (from this codebase)

| Resource | Guidance |
|---|---|
| OS | Ubuntu 22.04+ / Debian 12+ |
| CPU | 2 vCPU minimum (4 preferred if Playwright Chromium is enabled) |
| RAM | **2 GB minimum**; **4 GB+** if Next + uvicorn + Playwright share one host |
| Disk | **20 GB+** SSD; mount persistent volume at `/app/data` (and workspace) |
| GPU | Not required for OpenAI/Anthropic API mode. Required only if you self-host large local models |
| Ollama | Optional on the **same** VPS only; set `AI_PROVIDER=ollama` + `LOCAL_MODEL_URL=http://127.0.0.1:11434`. Laptop Ollama is unreachable |

### Run with the existing Docker image

```bash
# On the VPS (after cloning the repo and creating a host .env — never commit it)
docker build -t nexa:prod .
docker run -d --name nexa \
  --env-file /path/to/nexa.prod.env \
  -e PORT=8080 \
  -e CORS_ALLOWED_ORIGINS=https://YOUR_DOMAIN \
  -e BILLING_PUBLIC_BASE_URL=https://YOUR_DOMAIN \
  -e AUTH_PUBLIC_BASE_URL=https://YOUR_DOMAIN \
  -e AUTH_COOKIE_SECURE=true \
  -e AI_PROVIDER=openai \
  -p 127.0.0.1:8080:8080 \
  -v nexa-data:/app/data \
  -v nexa-workspace:/app/agent_workspace \
  nexa:prod
```

Put a host reverse proxy (Caddy or nginx) in front for TLS. Example Caddy on the host:

```caddy
YOUR_DOMAIN {
    reverse_proxy 127.0.0.1:8080
}
```

Internal container Caddy already splits `/api/*` + `/health` → uvicorn and `/*` → Next.

### Without Docker (same ports/scripts)

1. Python 3.12 venv + `pip install -r requirements.txt`
2. `cd frontend && npm ci && npm run build`
3. Export production env from [`.env.production.example`](.env.production.example)
4. Start API: `uvicorn app.main:app --host 127.0.0.1 --port 8420 --proxy-headers`
5. Start UI: `cd frontend && npx next start -H 127.0.0.1 -p 3000`
6. Terminate both on SIGTERM (see [`scripts/prod_start.sh`](scripts/prod_start.sh))

Do **not** expose 8420/3000/Ollama to `0.0.0.0` publicly — only the TLS proxy.

---

## Domain and HTTPS (prepare only — do not buy/change DNS here)

When a domain exists:

1. **DNS:** `A`/`AAAA` (or `CNAME`) for the apex/www → the VPS or platform target the owner chooses. Do not invent IPs.
2. **HTTPS:** Let’s Encrypt via Caddy/nginx-certbot or the platform’s managed TLS.
3. **Frontend public URL:** `https://YOUR_DOMAIN`
4. **API:** same origin (`NEXT_PUBLIC_API_BASE_URL=` empty in Docker build) → browser calls `https://YOUR_DOMAIN/api/...`
5. **Env that must match the public origin:**
   - `CORS_ALLOWED_ORIGINS=https://YOUR_DOMAIN`
   - `BILLING_PUBLIC_BASE_URL=https://YOUR_DOMAIN`
   - `AUTH_PUBLIC_BASE_URL=https://YOUR_DOMAIN`
   - `AUTH_COOKIE_SECURE=true`
   - `AUTH_RP_ID=YOUR_DOMAIN` (passkeys, if enabled)
   - OAuth redirect URIs in Google/etc. console → that origin

---

## Personal data processed (factual inventory)

Based on current features (not a legal opinion):

| Category | Examples in NEXA |
|---|---|
| Account | email, name, username, password hash, session cookies/tokens, OAuth subject ids, passkeys if enabled |
| Consents / legal | terms/privacy/license acceptance records |
| Chat / agent | message content, request ids, tool/agent step traces |
| Memory / profile | saved memory items, personalization/profile JSON |
| Knowledge / files | uploaded documents, attachment extracts, vectors metadata |
| Projects / workspace | agent sandbox files under `AGENT_WORKSPACE_DIR` |
| Plugins | encrypted plugin secrets, connection metadata, audit events |
| Billing | plan/subscription ids, Stripe customer/payment **references** (no card PAN/CVV stored), invoices metadata |
| Tokens | internal NEXA credit balances and ledger |
| Logs | request/error logs (secrets redacted by logging filter — still may contain user content) |
| Research | fetched page text / search queries |

**Owner/operator facts still needed for legal pages / possible Роскомнадзор notice (152-ФЗ):** legal name or entity name, status (individual / ИП / ООО), contact email/address, INN if applicable, country of establishment, who is the оператор ПДн, retention periods, purpose of processing, cross-border transfer details (e.g. OpenAI/Stripe processors). Do **not** invent these; do not file notices without the owner.

---

## Pre-publish checklist (blockers)

- [ ] Owner confirms host (VPS / Render / Railway) and accepts cost/limits
- [ ] Persistent volume for `/app/data` (Render Free is **not** durable)
- [ ] Cloud `AI_PROVIDER` + API key in host secrets (not Ollama-on-laptop)
- [ ] Public HTTPS origin set in CORS / AUTH / BILLING URLs
- [ ] SMTP configured **or** a deliberate temporary skip of email verification
- [ ] `AUTH_OWNER_EMAILS` / bootstrap policy locked before open registration
- [ ] Legal copy + operator details filled; privacy notice reviewed
- [ ] Stripe only if legal operator can accept RUB and keys are set
