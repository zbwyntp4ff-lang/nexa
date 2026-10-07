# NEXA Production Deployment

## Public URL

After the first successful Railway deploy, the permanent HTTPS URL is:

**https://\<your-service\>.up.railway.app**

(Record the exact URL from `railway domain` / Railway dashboard here after deploy.)

Frontend and Backend share this single origin (Caddy reverse proxy).

## Architecture

- **Provider:** Railway (Docker)
- **Image:** [`Dockerfile`](Dockerfile) — Next.js UI + FastAPI API + Caddy
- **Data:** JSON stores under `/app/data` (attach a Railway Volume at `/app/data`)
- **Auth:** Existing NEXA auth (`/api/v1/auth`) — do not disable for “open access”
- **AI:** Cloud provider via env (`AI_PROVIDER=openai` + `OPENAI_API_KEY`). Local Ollama is for development only.

```text
Internet → Railway HTTPS → Caddy :$PORT
                           ├─ /health, /api/* → uvicorn :8420
                           └─ /*              → next start :3000
```

## Required environment variables

Set in Railway → Variables (never commit real values):

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `production` |
| `AI_PROVIDER` | `openai` (or `anthropic`) |
| `OPENAI_API_KEY` | Required for real chat when using OpenAI |
| `OPENAI_MODEL` | e.g. `gpt-4o-mini` |
| `CORS_ALLOWED_ORIGINS` | Public HTTPS origin (same as the Railway URL) |
| `AUTH_SINGLE_USER` | `false` for team registration |
| `AUTH_COOKIE_SECURE` | `true` |
| `AUTH_COOKIE_SAMESITE` | `lax` |
| `AUTH_SKIP_EMAIL_VERIFICATION` | `true` unless SMTP is configured |
| `AUTH_BOOTSTRAP_FIRST_OWNER` | `true` for first account = owner |
| `MEMORY_STORE_PATH` | `data/memory_store.json` |
| `AUTH_STORE_PATH` | `data/auth_store.json` |
| `BILLING_STORE_PATH` | `data/billing_store.json` |
| `AGENT_WORKSPACE_DIR` | `agent_workspace` |
| `LOG_LEVEL` | `INFO` |

Optional: Stripe, Anthropic, SMTP — see [`.env.production.example`](.env.production.example).

## Deploy (first time)

```bash
npm install -g @railway/cli
railway login
railway init          # create / link project
railway up            # build + deploy from this directory
railway domain        # show / generate public HTTPS domain
```

Attach a volume to `/app/data` in the Railway service settings so auth/memory survive redeploys.

Set variables (especially `OPENAI_API_KEY` and `CORS_ALLOWED_ORIGINS`), then redeploy if needed:

```bash
railway variables set ENVIRONMENT=production AI_PROVIDER=openai AUTH_SINGLE_USER=false AUTH_COOKIE_SECURE=true
# Set secrets in the dashboard or:
# railway variables set OPENAI_API_KEY=...
railway up
```

## Redeploy / update

```bash
git add -A && git commit -m "describe change"
railway up
```

## Logs

```bash
railway logs
```

Or Railway dashboard → Deployments → View logs.

## Rollback

Railway dashboard → Deployments → select a previous successful deployment → **Redeploy**.

## Health check

`GET https://<public-url>/health` → `{ "status": "ok" }`

## Team access

1. Open the public URL.
2. First registered user becomes owner when `AUTH_BOOTSTRAP_FIRST_OWNER=true`.
3. Additional teammates register normally (`AUTH_SINGLE_USER=false`).
4. Optionally set `AUTH_OWNER_EMAILS` for developer UI access.
5. For email verification in production, configure SMTP and set `AUTH_SKIP_EMAIL_VERIFICATION=false`.

Do not share API keys with the team — keys stay in Railway variables only.

## Change domain

Railway dashboard → Settings → Networking → Custom Domain (add DNS CNAME as instructed). Update `CORS_ALLOWED_ORIGINS` and `BILLING_PUBLIC_BASE_URL` to the new origin.

## Recover after failure

1. `railway logs` — identify crash (missing env, OOM, bad build).
2. Confirm `/health` and volume mount.
3. Redeploy last good deployment or `railway up` after fix.
4. If auth store corrupted, restore `/app/data` from backup/volume snapshot.

## Local development (unchanged)

```bash
# API
uvicorn app.main:app --reload --port 8420

# UI
cd frontend && npm run dev   # http://localhost:4820
```

Do not point local `.env` at production secrets unless intentional.
