# NEXA Beta Release Gate

**Verdict: CONDITIONAL GO** (closed / invite beta only — not unrestricted open beta)

Date of gate checks: 2026-10-21. Security is **not** claimed to be fully proven.

## Install & run

### Local desktop (Electron)

```bash
# Backend deps
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium   # optional BrowserTool

# Frontend
cd frontend && npm ci && npm run electron:dev
# Electron sets NEXA_LOCAL_DESKTOP=1 and binds backend to 127.0.0.1
```

### Local API only

```bash
cp .env.example .env
# Set a real AI_PROVIDER + key (not mock for demos)
uvicorn app.main:app --host 127.0.0.1 --port 8420
cd frontend && npm ci && npm run dev
```

### Cloud / shared host (closed beta)

```bash
# Required (durable):
ENVIRONMENT=production
NEXA_STORAGE_MODE=persistent
TOKENS_ENFORCE=true
AI_PROVIDER=openrouter|openai|anthropic|gemini   # not mock
# + SMTP, AUTH_PUBLIC_BASE_URL, CORS_ALLOWED_ORIGINS, AUTH_COOKIE_SECURE=true
# Do NOT set: NEXA_LOCAL_DESKTOP, NEXA_ELECTRON_ALLOW_LAN_BIND, NEXA_ALLOW_PACKAGED_DEVTOOLS
```

Startup refuses unsafe durable configs via `app/config/production_guards.py`.

## Verified configuration matrix

| Setting | Local desktop | Cloud shared |
|---------|---------------|--------------|
| `TOKENS_ENFORCE` | optional false (single-user) | **true** |
| `NEXA_LOCAL_DESKTOP` | **1** (Electron) | **unset/0** (blocked if durable) |
| `AI_PROVIDER` | real or ollama | real (mock blocked if durable) |
| Backend bind | `127.0.0.1` | reverse proxy → app; no LAN Electron bind |
| Auth | optional | session required on protected routes |

## Known limitations

- `TOKENS_ENFORCE=false` disables multi-user Results/Build ACL — desktop/pytest only.
- OpenRouter model `openrouter/free` is unreliable; prefer a named chat model.
- Live web fetch: some hosts return 403/SSL/timeout — honest failure, no fake sources.
- Journal is scrubbed but task_id-scoped under enforce; not a full per-user audit log.
- Electron CSP still allows `'unsafe-inline'` scripts (mitigated by contextIsolation + sandbox).
- Invite-only / closed registration is **operational** (not fully encoded as product policy).
- Full LAN bind scan and live XSS against packaged CSP were **not** auto-tested.

## Test results (this gate)

```text
python -m pytest tests/test_beta_release_gate.py tests/test_game_creator.py \
  tests/test_security_phase6_final.py tests/test_build_engine.py -q
→ 25 passed

# Earlier security pack (Phase 6 final):
python -m pytest tests/test_security_phase6_final.py tests/test_phase6_beta.py \
  tests/test_desktop_phase4.py tests/test_cloud_isolation.py tests/test_security_part15.py -q
→ 49 passed

npx vitest run electron/__tests__/packaging.test.js
→ 10 passed
```

### Real model (not mock)

- Provider: OpenRouter (`openrouter/free` from local `.env` — **not recommended**)
- Sample 8 cases: pass_rate **0.75** (6/8), errors 0 — `data/eval_reports/beta_gate_model_eval.json`
- Tokens: recorded when API returns usage; cost_usd left null (not invented)

### Live compound E2E

- Script: `python scripts/phase6_live_e2e.py`
- Live search: **real** (3 sources fetched; some URLs 403/timeout skipped)
- PPTX / XLSX / DOCX: **real** creation + library verify
- Research: **not mocked**
- Report: `data/eval_reports/beta_live_e2e.json` — status `completed`

## Route inventory (Results / Build / files / projects)

| Route | Auth when enforce | Isolation |
|-------|-------------------|-----------|
| `GET /api/v1/results/{id}` (+ `/download`) | required | owner ACL |
| `GET /api/v1/projects/{id}` | required | ManifestStore user bucket |
| `POST /api/v1/agent` | required | server stamps `user_id` |
| `POST /api/v1/build/run` | required | stamps `user_id`; denies cross-user edit |
| `GET /api/v1/build/projects` | required | filtered to owner |
| `GET /api/v1/build/projects/{id}` | required | owner ACL |
| `GET /api/v1/build/preview/...` | required | owner ACL (fixed this gate) |
| `GET /api/v1/build/export/...` | required | owner ACL (fixed this gate) |
| Attachments | required | per-user |

When `TOKENS_ENFORCE=false`, auth is optional and ownerless Results remain readable (documented desktop mode).

## Rollback

1. Redeploy previous known-good git tag / container image.
2. Restore `data/` backups (auth store, build_projects.json, results sandbox) from last snapshot.
3. Set `TOKENS_ENFORCE=true` if it was flipped off.
4. Revoke sessions (auth store rotation / restart with empty session table if using SQL auth).
5. Rotate provider API keys if logs suggest exposure.

## Electron notes (manual if needed)

- Static review: `contextIsolation`, `nodeIntegration: false`, `sandbox: true`, allowlisted preload IPC.
- Packaged DevTools gated; LAN bind opt-in only.
- **Not auto-verified:** attaching a remote debugger to a packaged build, or probing the LAN NIC while Electron runs.

## Fixes in this gate

- Build preview/export/list ACL under `TOKENS_ENFORCE` + `user_id` on `BuildProjectRecord`
- Durable production rejects `NEXA_LOCAL_DESKTOP` / LAN bind / packaged DevTools flags
- Journal global dump returns empty under enforce without `task_id`

## Decision

**CONDITIONAL GO** for **closed/invite beta** if operators enforce the cloud matrix above and avoid `openrouter/free`.

**NO-GO** for unrestricted public open beta until invite/auth policy is locked and a named production model is configured end-to-end.
