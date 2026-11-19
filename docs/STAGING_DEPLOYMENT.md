# NEXA — Staging Deployment Preparation

**Status:** prepared, **not published**. This document does not deploy, buy services, or change DNS.

**Related:** [`OPEN_BETA_READINESS.md`](OPEN_BETA_READINESS.md) (GO/NO-GO), [`STORAGE_MATRIX.md`](STORAGE_MATRIX.md), [`../DEPLOYMENT.md`](../DEPLOYMENT.md).

---

## 1. Architecture audit (current code)

### One Docker container?

**Yes.** [`Dockerfile`](../Dockerfile) builds a single runtime image:

| Process | Role | Bind |
|---------|------|------|
| Caddy | Public edge (gzip + reverse proxy) | `$PORT` (default 8080) |
| uvicorn `app.main:app` | FastAPI API | `127.0.0.1:$NEXA_API_PORT` (8420) |
| `next start` | Next.js UI | `127.0.0.1:$NEXA_WEB_PORT` (3000) |

Entrypoint: [`scripts/prod_start.sh`](../scripts/prod_start.sh).  
Caddyfile: [`deploy/Caddyfile`](../deploy/Caddyfile) — `/health` + `/api/*` → API; everything else → Next.

**No second app service is required** for core chat/auth/agent. External dependencies:

| Need | Separate service? |
|------|-------------------|
| SMTP mail delivery | **Yes** (provider outside the image) |
| Cloud LLM API | **Yes** (OpenRouter / OpenAI / Anthropic / Gemini) |
| Persistent disk | **Yes** (platform volume) — or managed Postgres |
| Managed Postgres | Optional (instead of SQLite on the volume) |
| Stripe / OAuth | Optional; not required for staging smoke |
| Redis / queue workers | **Not used** by current core paths |
| Desktop / Ollama | **Forbidden** on staging (`NEXA_LOCAL_DESKTOP` refused) |

### How the platform port is obtained

The host sets `PORT`. Caddy listens on `:{$PORT:8080}`. Platforms (Render, Railway, etc.) inject `PORT`; the container does not hard-require 8080 externally.

### Where data lives / restart survival

| Data | Store | Survives restart? |
|------|-------|-------------------|
| Accounts, sessions, verify codes | JSON `AUTH_STORE_PATH` under `/app/data` | **Only with volume** |
| Conversations + SQL memory | `DATABASE_URL` (SQLite file or Postgres) | **Volume or managed DB** |
| Tokens, profiles, billing, plugins, knowledge | JSON under `/app/data` | **Volume** |
| Agent / build artifacts | `AGENT_WORKSPACE_DIR` | Volume recommended |
| Image attachments | Image bytes + owner metadata sidecars under `ATTACHMENT_STORAGE_DIR` | Yes until TTL when volume is mounted; metadata/signature are checked on restore |
| Document attachments | Extracted text/chunks in memory; source file removed after parsing | No; intentionally transient across process restart |
| Workflows | In-memory | **No** — keep `WORKFLOWS_ENABLED=false` |
| Rate-limit counters | In-process | Reset on restart |

Migrations: `CREATE TABLE IF NOT EXISTS` on FastAPI lifespan — **non-destructive**. Do not run wipe scripts against staging data.

### Background work inside the API process

- Attachment cleanup loop (asyncio task)
- Optional warm-inference task  
No separate worker container is required for staging smoke.

### `render.yaml` (Free) is **not** staging

Root [`render.yaml`](../render.yaml) is a **Free / ephemeral** smoke profile (`NEXA_STORAGE_MODE=ephemeral`, `AI_PROVIDER=mock`, `AUTH_SKIP_EMAIL_VERIFICATION=true`, `EMAIL_PROVIDER=console`).  

`NEXA_PUBLIC_BETA=true` **refuses** that combination at startup. Use [`deploy/render-staging.example.yaml`](../deploy/render-staging.example.yaml) instead.

---

## 2. Recommended path (lowest cost — verify pricing yourself)

**Do not assume any platform is free.** Current public-beta guards need **persistent storage**, so classic “Free web service with no disk” tiers are **out of scope** for this staging profile.

**Simplest staging stack (minimal moving parts):**

1. **One Docker Web Service** (this repo’s Dockerfile).
2. **One persistent disk** mounted at `/app/data` (SQLite + JSON stores).
3. **Platform HTTPS URL** (`*.onrender.com` / `*.up.railway.app` / VPS + Caddy) — no custom DNS required for first smoke.
4. **SMTP** from an email provider you already have or a trial you approve (costs vary; check their current terms).
5. **Named cloud model** with a pay-as-you-go key (usage billed by the AI vendor).

**Ordered options (operator picks after checking live pricing):**

| Option | Fit | Notes |
|--------|-----|-------|
| A. Render **paid** web + disk | Good | Adapt `deploy/render-staging.example.yaml`; Free plan lacks disk |
| B. Railway + volume at `/app/data` | Good | `railway.toml` + `deploy/railway.env.example` |
| C. Small Linux VPS + Docker | Good | Full control; you pay the VPS; see `DEPLOYMENT.md` |
| D. Render Free / ephemeral | **Unsuitable** for `NEXA_PUBLIC_BETA` | Data loss + guards fail |

Prefer **A or B** for least ops. Prefer **C** if you already have a VPS.

---

## 3. Required environment (staging)

Template (no secrets): [`.env.staging.example`](../.env.staging.example).

| Variable | Required value / rule |
|----------|------------------------|
| `NEXA_PUBLIC_BETA` | `true` |
| `ENVIRONMENT` | `production` |
| `NEXA_STORAGE_MODE` | `persistent` |
| `TOKENS_ENFORCE` | `true` |
| `AUTH_SKIP_EMAIL_VERIFICATION` | `false` |
| `AUTH_COOKIE_SECURE` | `true` |
| `AUTH_SINGLE_USER` | `false` |
| `EMAIL_PROVIDER` | `smtp` |
| `SMTP_HOST` / `EMAIL_FROM` | set |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | set if provider requires auth |
| `AI_PROVIDER` | not `mock` |
| Model id | **not** `openrouter/free` (named model only) |
| Matching `*_API_KEY` | set in platform secret store |
| `AUTH_PUBLIC_BASE_URL` | exact HTTPS origin |
| `CORS_ALLOWED_ORIGINS` | exact HTTPS origin |
| `BILLING_PUBLIC_BASE_URL` | same origin (even if billing unused) |
| `MEMORY_BACKEND` | `sql` |
| `DATABASE_URL` | `sqlite:///data/nexa-staging.db` or Postgres URL |
| `WORKFLOWS_ENABLED` | `false` |
| `NEXA_LOCAL_DESKTOP` | **unset** |
| `NEXA_AI_KILL_SWITCH` | `false` until testing kill-switch |

Secrets: platform dashboard / secret store only. **Never** commit filled env files. **Never** copy real keys from a developer `.env` into git.

Preflight (redacts secrets):

```bash
# After exporting staging env (or on the host):
python scripts/staging_preflight.py
```

---

## 4. Build & run commands

### CI image validation (no registry push / no deploy)

Full notes: [`DOCKER_IMAGE_VALIDATION.md`](DOCKER_IMAGE_VALIDATION.md).  
Workflow: [`.github/workflows/docker-image.yml`](../.github/workflows/docker-image.yml).

```bash
# Same checks the workflow runs (requires local Docker):
chmod +x scripts/prod_start.sh scripts/ci_docker_smoke.sh
./scripts/ci_docker_smoke.sh
```

Uses production-like env (`NEXA_PUBLIC_BETA=true`, SMTP host set, named OpenRouter model, **not** mock). Placeholder API key only — not a real secret. Does **not** push images or deploy.

**Repo setup required:** push to GitHub with Actions enabled, then **Actions → Docker image validation → Run workflow** (`workflow_dispatch`), or push/PR matching the workflow path filters. Do not treat this as passed until that run (or a local Docker smoke) is green.

### Local image build (when Docker is installed)

```bash
docker build -t nexa-staging:local .
```

### Local compose dry-run (no public publish)

```bash
cp docker-compose.staging.example.yml docker-compose.staging.yml
cp .env.staging.example .env.staging.local
# Edit .env.staging.local: SMTP, AI key, AUTH_PUBLIC_BASE_URL / CORS to your URL
docker compose -f docker-compose.staging.yml --env-file .env.staging.local up --build
curl -fsS http://127.0.0.1:8080/health
```

`docker-compose.staging.yml` and `.env.staging.local` are gitignored.

### Entrypoint behavior

1. `chown` volume dirs if started as root, then drop to user `nexa` for app processes.
2. Start uvicorn → wait until `/health` on API port (fail if API dies — e.g. `ProductionConfigError`).
3. Start Next.js.
4. Start Caddy on `$PORT`.
5. On `SIGTERM`/`SIGINT`, terminate Caddy + API + Web (graceful shutdown).

Health:

```bash
curl -fsS https://<staging-origin>/health
# Expect JSON with status ok|degraded, storage_mode=persistent, database_ok=true
```

Dockerfile `HEALTHCHECK` already curls `http://127.0.0.1:${PORT}/health`.

### Platform (after explicit approval — not done in this prep)

1. Create service from Dockerfile.
2. Attach **persistent disk** at `/app/data` (required).
3. Set env from `.env.staging.example` / `deploy/render-staging.example.yaml`.
4. Deploy → copy HTTPS URL → set `CORS_*` / `AUTH_PUBLIC_BASE_URL` / `BILLING_PUBLIC_BASE_URL` → restart.
5. Run post-deploy checks (§6).

---

## 5. SMTP setup (staging)

1. Create a transactional mailbox / SMTP credentials at your chosen provider.
2. Set on the host only:

```text
EMAIL_PROVIDER=smtp
EMAIL_FROM=noreply@your-domain-or-provider
SMTP_HOST=...
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_USE_TLS=true
```

3. Keep `AUTH_SKIP_EMAIL_VERIFICATION=false`.
4. Register a **test** address you control; confirm the message arrives.
5. If SMTP is missing, startup **fails** under `NEXA_PUBLIC_BETA` (no console fake-success).

---

## 6. Post-deploy checks (real staging only)

| Check | Expect |
|-------|--------|
| `GET /health` | `status` ok (or degraded only if DB ping fails — should not) |
| Register test user | 200 + email sent |
| Verify email | login succeeds only after verify |
| Chat (named model) | real reply; not mock/free stub |
| Agent with parallel cap | second parallel run limited |
| Logout | protected routes 401/403 |
| Second user | cannot read first user’s results/builds |
| Kill switch on/off | chat blocked then restored |
| Redeploy / restart | accounts still present (volume proof) |

Full matrix: `docs/OPEN_BETA_READINESS.md`.

---

## 7. Known limits & possible costs

| Topic | Fact |
|-------|------|
| Persistent disk | Usually **paid** on managed PaaS; verify current plan prices |
| AI tokens | Billed by provider; staging should use a cheap named model and low rate limits |
| SMTP | Provider-dependent (trial / free tier / paid) — check their terms; not claimed free here |
| Playwright/Chromium in image | Increases image size/RAM; may OOM on tiny instances |
| Cold start | Depends on plan; not an SLA |
| Custom domain / DNS | **Out of scope** until separately approved |
| `data/model_selection.json` | Do **not** ship a pin to `openrouter/free` on the volume |

---

## 8. Verification status (this preparation pass)

### Verified locally (this workstation)

| Item | Result |
|------|--------|
| Architecture / Dockerfile / Caddy / lifespan migrate / guards | Reviewed against current code |
| Staging templates | `.env.staging.example`, `deploy/render-staging.example.yaml`, compose example, railway env |
| SIGTERM handling in `prod_start.sh` | Fixed (no longer `exec caddy` over the trap) |
| Unit/guard tests | See report in the agent session (open-beta / production_guards) |
| Docker CLI | **Not installed** on this machine — image build **not** executed here |
| `scripts/ci_docker_smoke.sh` | Exits **127** here (`docker` missing) — **not a pass** |
| GitHub Actions Docker workflow | Present; **not run** (no git remote / no `gh` on this host) |
| `scripts/staging_preflight.py` with synthetic staging env | Guards **OK** (no secrets); warns if AI key unset |
| Guard/unit tests | open-beta / production / beta-gate / auth — see latest session pytest count |
| Real staging deploy | **Not performed** (by instruction) |

### Requires real staging

- Platform account + disk + HTTPS URL
- Working SMTP end-to-end
- Named model credentials that authorize the chosen model
- Full smoke matrix + restart durability proof

### Blockers before “staging GO”

1. Operator approval to create a **non-ephemeral** host (disk may incur cost).
2. SMTP credentials.
3. Named AI API key that works for the configured model.
4. Docker build verification on a machine that has Docker (or rely on platform remote build).

---

## 9. Explicit non-actions

- No public deploy executed from this prep.
- No DNS changes.
- No paid services purchased by the agent.
- Root `render.yaml` Free blueprint left unchanged (still for ephemeral smoke only).
