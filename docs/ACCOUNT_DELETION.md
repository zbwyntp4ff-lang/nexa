# Account deletion

`DELETE /api/v1/auth/account` with JSON body `{"confirm":"DELETE"}` (case-insensitive).

## Who can call it

Only the authenticated session owner (`Authorization: Bearer` / session cookie). There is no admin cross-user delete via this endpoint.

## Removed immediately from live application stores

| Data | Store |
|------|--------|
| User record + all sessions | Auth JSON (`AUTH_STORE_PATH`) |
| Memory items | SQL / configured memory backend |
| Knowledge documents + vectors | Knowledge JSON stores |
| Knowledge-core feedback rows | Feedback JSONL |
| Synced conversations | SQL `conversations` |
| Plugin connections + encrypted secrets | Plugin JSON + key |
| In-process workflows for that user | Workflow engine RAM |
| Profile personalization | Profile JSON |
| Token / credit ledger | Token JSON |
| In-memory attachments stamped with `user_id` | Attachment manager |

## May remain after live wipe (not claimed as deleted)

| Area | Behavior |
|------|----------|
| Operator backups / disk snapshots / Postgres PITR | Remain until **operator** retention expires; NEXA wipe does not purge backups |
| Log aggregators (host, Render, Railway) | May retain request metadata; scrubbing is ops-owned |
| Other devices' browser / Electron localStorage | Not remotely wiped; this client clears chat bucket on delete/logout |
| CDN edge caches | N/A for private JSON/SQL; no CDN purge API |

## External providers (separate deletion / retention)

| Provider | NEXA action | Operator / user action |
|----------|-------------|-------------------------|
| OpenAI / Anthropic / Gemini / OpenRouter | Stops sending new traffic for deleted user | Provider logs/prompts follow **their** retention; contact provider if erasure required |
| SMTP / email | No further mail to that address | Mailbox copies of verification codes may remain with mail host |
| Stripe (if enabled) | App billing store row cleared; Stripe Customer not auto-deleted | Delete/anonymize Customer in Stripe Dashboard or API |
| OAuth IdPs (Google/GitHub/…) | Local link removed with user | Revoke app access in the IdP account settings |
| Replicate / fal (video) | No further jobs | Provider job history per their policy |

Do **not** advertise “guaranteed erasure from all backups and providers” unless those pipelines are implemented and verified separately.
