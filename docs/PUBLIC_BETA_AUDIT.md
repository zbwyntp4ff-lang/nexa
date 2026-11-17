# NEXA — Public Beta Security & Operations Audit

**Audit date:** 2026-11-17  
**Reviewed ref:** `fix/security-and-reliability-non-billing`  
**Reviewed commit:** `5c342a6000aa97ca17fd52a7b1fc18bdebde55e6`  
**Verdict:** **NO-GO for open public beta**. This is a repository/configuration review, not a penetration test or live staging validation.

## Executive summary

The latest GitHub Actions CI run is green: Python tests, frontend tests + production build, Electron IPC packaging tests, and Docker build/smoke all completed successfully. The attached dependency audit artifacts show **0 known Python advisories** and **9 npm moderate advisories** (0 high, 0 critical).

Green CI does not establish production readiness. The repository's own `OPEN_BETA_READINESS.md` correctly records that no staging deployment or end-to-end public-beta smoke has been completed.

## Findings

### P1 — Browser session bearer token is exposed to JavaScript

**Evidence**
- `app/api/routes/auth.py` returns `session_token` in JSON from login, owner setup, and device-login completion, while also setting an HttpOnly cookie.
- `frontend/src/lib/session-token.ts` writes the token to `window.localStorage` under `nexa_session_token`.
- `frontend/src/lib/api.ts` reads that token and sends it as an Authorization bearer token.

**Risk**
Any successful same-origin script injection or compromised browser extension with page access can read the persistent bearer token and replay the session. The HttpOnly cookie does not protect the duplicate token stored in localStorage.

**Recommended remediation**
- Use the HttpOnly cookie as the browser's only session credential; do not return bearer tokens in browser-facing JSON responses.
- If Electron genuinely needs a bearer token, separate the desktop auth flow and store the credential in an OS-protected store (or keep it in memory where feasible), not shared browser localStorage.
- Add regression tests proving browser login does not persist a bearer token in localStorage and cookie logout/revocation remains correct.

**Status:** Confirmed code-level exposure; exploitability still depends on a script-injection or client-compromise path. No such exploit was demonstrated in this review.

### P1 — Public rate limiting requires an edge control

**Evidence**
- `app/web/rate_limit.py` and `app/auth/rate_limit.py` use in-process sliding-window counters.
- `docs/EDGE_RATE_LIMITING.md` states these are single-process controls and that the shipped Caddy configuration has no distributed rate-limit module.

**Risk**
Counters reset on restart and do not coordinate across instances. They are not sufficient protection against distributed abuse, credential stuffing, or high-volume API traffic on a public service.

**Required before public beta**
Place a trusted CDN/WAF or reverse-proxy rate limiter in front of the app; configure tighter limits for registration, login, password reset, and expensive AI endpoints. Verify the proxy-to-ASGI client-IP trust chain and spoofed-forwarded-header behavior in the actual deployment.

**Status:** Documented operational gap; staging edge behavior not tested.

### P1 — Persistent JSON stores constrain safe scaling and recovery

**Evidence**
- `docs/STORAGE_MATRIX.md` lists auth users/sessions, profiles, tokens, billing, plugin state, knowledge documents, and other state in JSON/file stores.
- `app/auth/store.py` protects writes with a process-local thread lock and atomically replaces a JSON file.
- `docs/STAGING_DEPLOYMENT.md` recommends one app container with a persistent volume; workflows and rate-limit counters are in-memory.

**Risk**
A thread lock is not a cross-process or cross-instance transaction mechanism. Running multiple API workers or replicas against the same JSON files can cause lost updates or inconsistent state. A persistent disk alone is not a backup.

**Required before scaling beyond one app process**
Keep a documented single-process/single-instance constraint for the first beta, or migrate shared mutable stores to a transactional database with proper concurrency control before enabling multiple workers/replicas. Define backup frequency, retention, encryption/access controls, and complete restore testing.

**Status:** Architecture constraint confirmed; no multi-instance load test or restore drill completed.

### P1 — Staging release gates are still blocked

**Evidence**
- `docs/OPEN_BETA_READINESS.md` records no staging deployment and marks the smoke matrix NOT RUN.
- SMTP is not configured in the documented developer environment.
- The documented named OpenRouter model probe returned `authentication_error`; the Anthropic probe returned `provider_unavailable`. The successful `openrouter/free` probe is explicitly not accepted as a public-beta model.
- The public-beta guard requires persistent storage, verified email, a named model, and secure production settings.

**Required before public beta**
Deploy an isolated staging environment only after the owner approves the platform/cost and supplies credentials through the platform's secret manager. Complete registration/email verification, real named-model chat, authenticated agent flow, logout, two-user isolation, kill-switch recovery, backup/restore, and edge-rate-limit checks. Do not use mock or `openrouter/free` as the production model.

**Status:** Blocking; no staging deploy or paid resource was initiated during this audit.

### P2 — npm moderate advisories remain

**Evidence**
The latest CI artifact `nexa-npm-audit-report` contains **9 moderate advisories**, including the `minimatch` dependency chain, `electron-builder` / `app-builder-lib`, and `shadcn` / `ts-morph`. The CI gate `npm audit --audit-level=high` passes because there are no high or critical advisories; it does not mean npm audit is clean.

**Required action**
Review each advisory's reachability and fix availability. Upgrade or replace affected dependencies where compatible, run frontend tests, production build, Electron packaging tests, and re-export a fresh npm audit artifact. If any moderate advisory is accepted, record why and the mitigation.

**Status:** Open; high/critical gate passes, moderate findings remain.

## Verified checks from the latest CI run

| Check | Result |
|---|---|
| Python test/security/evaluation job | Passed |
| Frontend unit tests | Passed |
| Frontend production build | Passed |
| Electron IPC packaging test | Passed |
| npm high/critical audit gate | Passed |
| Docker image build + smoke | Passed |
| Python dependency audit artifact | 0 advisories |
| npm dependency audit artifact | 9 moderate; 0 high; 0 critical |
| Real staging smoke | Not run |
| SMTP delivery | Not verified |
| Named production model | Not verified successfully |
| Multi-user staging isolation | Not run |
| Backup restore drill | Not run |
| Public edge rate-limit test | Not run |

## Release decision

**Do not open public registration yet.** The codebase has a substantially stronger automated baseline, but the remaining P1 items and staging gates must be addressed first.

Suggested order:
1. Remove browser-accessible bearer-token persistence while preserving the Electron login flow.
2. Decide and enforce the single-instance storage constraint for beta; document the supported deployment topology.
3. Select and configure trusted edge rate limiting.
4. Resolve or explicitly accept the 9 moderate npm advisories.
5. Obtain approval for a low-cost isolated staging deployment and complete the smoke/restore matrix.
6. Re-run the full audit against the exact release commit.

## Scope and limitations

- No changes were made to billing, Stripe, subscriptions, payments, token charging, or balances.
- No deployment, DNS change, paid infrastructure, paid model call, or production secret was used for this audit.
- CI results were read from GitHub Actions; this review did not execute the application on the user's computer.
- This is a focused repository/configuration audit. It is not a formal penetration test, external attack simulation, legal/privacy review, or proof of runtime security.
