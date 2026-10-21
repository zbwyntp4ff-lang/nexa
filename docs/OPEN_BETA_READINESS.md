# NEXA — Open Public Beta Readiness

**Verdict: NO-GO for open public beta staging smoke** until a real staging host is deployed with SMTP + a working named (non-`free`) model.  
Prior code/guard work remains a **CONDITIONAL GO** for *invite-or-open signup after operators pass the matrix* — that is not the same as a completed staging smoke.

**Deploy prep:** [`STAGING_DEPLOYMENT.md`](STAGING_DEPLOYMENT.md) (single-container Docker, disk, env, SMTP — no publish yet).

This document separates **verified facts**, **automated checks**, **manual/staging steps**, and **blockers**. Local unit tests are **not** staging validation.

---

## 1. Audit summary (facts)

### Already implemented
- Self-registration (`POST /api/v1/auth/register`) when `AUTH_SINGLE_USER=false`
- Email verification flow (must be enabled for public beta)
- Login / logout / session cookie (`HttpOnly`, SameSite configurable)
- Forgot / reset password
- Results ACL + Build preview/export ACL under `TOKENS_ENFORCE=true`
- Agent stamps `user_id` from session (not client metadata)
- API rate limit middleware + auth register/login limiters
- Internal token/credit charges when enforce is on
- Durable production / open-beta startup guards
- Agent parallel cap (`AGENT_MAX_PARALLEL_PER_USER`)
- Provider kill switch (`NEXA_AI_KILL_SWITCH`)

### Gaps hardened in staging-prep pass
| Item | Change |
|------|--------|
| SMTP required under public cloud | `EMAIL_PROVIDER=smtp` + `SMTP_HOST` + `EMAIL_FROM` in `production_guards` |
| No silent console fallback on public hosts | `build_email_service` raises if smtp incomplete under public/durable |
| Account enumeration | Forgot/resend public responses no longer expose `code_expires_at` / `already_verified` differently for known emails |
| Staging env template | `.env.staging.example` (no secrets) |

### Public routes (must stay public)
- `/health`, auth register/login/forgot/reset, legal docs, static marketing
- Build preview **requires auth when enforce** (same-origin cookie)

### Still operational (not fully automated)
- Invite-only vs fully open marketing policy
- Edge rate limits (CDN/WAF) beyond in-process windows
- Stripe live onboarding / legal entity
- Manual Electron LAN/XSS probe
- **Real staging deploy + SMTP mailbox + paid/named model credentials**

---

## 2. Required environment (staging / open public beta)

Exact required set (secrets never committed; values not printed here):

```bash
NEXA_PUBLIC_BETA=true
ENVIRONMENT=production
NEXA_STORAGE_MODE=persistent
TOKENS_ENFORCE=true
AUTH_SINGLE_USER=false
AUTH_SKIP_EMAIL_VERIFICATION=false
AUTH_COOKIE_SECURE=true
AUTH_PUBLIC_BASE_URL=https://STAGING_OR_BETA_ORIGIN
CORS_ALLOWED_ORIGINS=https://STAGING_OR_BETA_ORIGIN
EMAIL_PROVIDER=smtp
SMTP_HOST=<operator>
SMTP_PORT=587          # or provider port
SMTP_USERNAME=<operator>
SMTP_PASSWORD=<secret>
EMAIL_FROM=<operator>
AI_PROVIDER=openrouter   # or openai / anthropic / gemini
OPENROUTER_MODEL=openai/gpt-4o-mini   # named — NOT openrouter/free
OPENROUTER_API_KEY=<secret>           # must authorize the named model
MEMORY_BACKEND=sql
DATABASE_URL=sqlite:///data/nexa-staging.db   # or Postgres
WORKFLOWS_ENABLED=false
AGENT_MAX_PARALLEL_PER_USER=2
NEXA_AI_KILL_SWITCH=false
ALLOW_MODEL_FALLBACK=false
# MUST be unset/0:
# NEXA_LOCAL_DESKTOP
# NEXA_ELECTRON_ALLOW_LAN_BIND
# NEXA_ALLOW_PACKAGED_DEVTOOLS
```

Template file: `.env.staging.example` (copy to host secret store only).

Startup refuses unsafe combinations via `app/config/production_guards.py`.

### Local desktop (not open beta / not staging)
```bash
NEXA_PUBLIC_BETA=false   # or unset
# Electron may set NEXA_LOCAL_DESKTOP=1 and bind 127.0.0.1
```

### Local `.env` probe (this workstation — NOT staging)

| Flag | Observed (no secrets) |
|------|------------------------|
| `ENVIRONMENT` | `development` |
| `NEXA_PUBLIC_BETA` | unset |
| `TOKENS_ENFORCE` | unset (defaults apply in code; not staging profile) |
| `AUTH_SKIP_EMAIL_VERIFICATION` | `true` |
| `EMAIL_PROVIDER` | `console` |
| `SMTP_HOST` | unset |
| `AI_PROVIDER` | `openrouter` |
| `OPENROUTER_MODEL` | `openrouter/free` (**banned** for public beta) |
| `data/model_selection.json` | pins `openrouter/free` |
| OpenRouter API key | present |
| Anthropic API key | present |
| SMTP password | unset |

**Conclusion:** this machine is a developer profile. It must not be called a staging environment.

---

## 3. Email verification

### Automated / code-verified
- Unverified users cannot login (`EmailNotVerifiedError`) — covered in `tests/test_auth.py`
- Code reuse rejected; expiry / attempt limits exercised in auth unit tests
- Resend cooldown exists in `AuthService`
- Public forgot/resend responses neutralized against simple field enumeration (unit: `test_resend_and_forgot_do_not_enumerate`)
- Under `NEXA_PUBLIC_BETA`, missing SMTP fails startup (guard) instead of pretending mail was sent via console

### Blocker (staging)
- **SMTP is not configured on this workstation** (`EMAIL_PROVIDER=console`, `SMTP_HOST` unset).  
  That is a **hard blocker** for staging smoke steps 1–2. Do **not** fake delivery with console on a public host.

### Manual on real staging (required)
1. Register test user → message arrives in real inbox
2. Confirm link/code works once; reuse fails; expired code fails
3. Resend works after cooldown
4. Unverified session cannot hit protected chat/agent routes
5. Confirm forgot/resend JSON shape is identical for known vs unknown emails

---

## 4. Real model / spend / kill switch

### Automated
```text
python -m pytest tests/test_open_beta_readiness.py::test_kill_switch_blocks_gateway \
  tests/test_open_beta_readiness.py::test_agent_parallel_cap -q
```
- Kill switch → `GatewayError` / `model_unavailable` (passed)
- Agent parallel cap raises `AgentBusyError` when over limit (passed)

### Live probes from this workstation (not staging; secrets not printed)

| Probe | Result |
|-------|--------|
| Gateway with local selection `openrouter/free` | `RESULT=OK`, ~8.0s, reply contained `ping-ok` — **not acceptable for public beta** |
| Forced selection `openai/gpt-4o-mini` (OpenRouter) | `RESULT=GATEWAY_ERROR` / `authentication_error` (“provider rejected the credentials”) |
| Forced `anthropic` / `claude-3-5-haiku-latest` | `RESULT=GATEWAY_ERROR` / `provider_unavailable` |
| `NEXA_AI_KILL_SWITCH=true` then chat | `KILL_SWITCH=BLOCKED` / `model_unavailable` |

**Cost:** not invented. Named OpenRouter call did not succeed here; free-route success is not a quality or billing proof. Measure spend on the provider dashboard after a successful named-model call on staging.

**Spend / concurrency enforcement:** token ledger + `TOKENS_ENFORCE`, optional `FREE_TIER_*`, and `AGENT_MAX_PARALLEL_PER_USER` are implemented in code; **not** load-tested on a staging host in this pass.

---

## 5. Staging smoke checklist (8 steps)

**Status: NOT RUN** — no staging deployment was performed (per instruction: prepare config and stop before real deploy; no public deploy / DNS / paid infra without permission).

| # | Step | Status |
|---|------|--------|
| 1 | Register new user | blocked — needs staging + SMTP |
| 2 | Receive + confirm email | blocked — SMTP |
| 3 | Login + protected chat | blocked |
| 4 | Real named-model reply | blocked — staging + working named credentials |
| 5 | Agent run with parallel cap | blocked |
| 6 | Create/download file (if enabled) | blocked / N/A until staging policy set |
| 7 | Logout → protected routes deny | blocked |
| 8 | Second-user data isolation | blocked |
| 9 | Kill-switch on/off recovery | blocked on staging; **unit/live local kill-switch code path OK** |

Use only test accounts and low volume when staging exists.

---

## 6. What was done vs automated vs manual

### Done in this pass (repo)
- SMTP required in public-cloud guards; refuse console fallback on public/durable
- Enumeration hardening for forgot/resend public responses
- `.env.staging.example` added
- Unit tests updated/added for SMTP requirement + non-enumeration
- Local env + live provider probes recorded honestly above
- **Stopped before any staging/public deploy**

### Automated commands & results
```text
python -m pytest tests/test_open_beta_readiness.py tests/test_production_guards.py \
  tests/test_beta_release_gate.py -q
```
**Result (this pass): 20 passed**

Additional recommended (not re-run as “staging”):
```text
python -m pytest tests/test_security_phase6_final.py tests/test_cloud_isolation.py \
  tests/test_auth.py -q
npx vitest run electron/__tests__/packaging.test.js
```

### Manual / operator (still required)
- Provision staging host + HTTPS + persistent volume
- Fill `.env.staging.example` secrets (SMTP + named model key that authorizes the chosen model)
- Ensure `data/model_selection.json` on the host does **not** pin `openrouter/free` (or delete and set env-only named model)
- Run the 8–9 smoke steps with two test users
- Backup restore drill once
- Edge rate-limit smoke

---

## 7. Remaining blockers

1. **No staging environment deployed** (config prepared only)
2. **SMTP unset** — email verification cannot be proven end-to-end
3. **Named model not proven with current keys** — OpenRouter named model returned `authentication_error`; Anthropic returned `provider_unavailable`; local pin remains `openrouter/free`
4. Full smoke matrix (register → verify → chat → agent → logout → isolation → kill-switch) **not executed on staging**

---

## 8. GO / CONDITIONAL GO / NO-GO

| Scope | Verdict |
|-------|---------|
| Code + startup guards for open-beta *profile* | **CONDITIONAL GO** — after operators set the env matrix and SMTP/named model |
| **Staging smoke before open beta** (this task) | **NO-GO** |

### Flip staging to GO when ALL are true
- [ ] Staging host boots with `NEXA_PUBLIC_BETA=true` (no `ProductionConfigError`)
- [ ] SMTP verification works end-to-end for a test mailbox
- [ ] Named production model answers chat (not mock / not `openrouter/free`)
- [ ] Smoke steps 1–9 recorded with timestamps / HTTP statuses (no secret dumps)
- [ ] Two-user isolation observed on staging
- [ ] Kill switch toggled on staging and restored
- [ ] Backups verified once

### Keep NO-GO if any
- `TOKENS_ENFORCE=false` on the public/staging host
- `NEXA_LOCAL_DESKTOP=1` on the host
- Mock or `openrouter/free` as the live model
- Email verification skipped or console-only mail
- Ephemeral storage for accounts

---

## 9. Launch steps (only after staging GO)

1. Set secrets + `NEXA_PUBLIC_BETA=true` on the intended host
2. Deploy behind HTTPS (explicit permission required for public DNS)
3. Smoke: register → verify email → chat → agent file → logout
4. Monitor `/health`, provider errors, 429 rates
5. Keep `NEXA_AI_KILL_SWITCH` ready
