# Backup and restore (operator)

NEXA does **not** ship an automated cloud backup product. For a public durable
host you must schedule backups of:

| Path / resource | Contents |
|-----------------|----------|
| `DATABASE_URL` (SQLite file or Postgres) | Conversations, SQL memory |
| `AUTH_STORE_PATH` | Users, sessions, passkey metadata |
| `TOKEN_STORE_PATH` / `PROFILE_STORE_PATH` / `BILLING_STORE_PATH` | Credits, profiles, billing |
| `PLUGIN_STORE_PATH` + `PLUGIN_KEY_PATH` | Plugin state + encryption key |
| `KNOWLEDGE_*` JSON paths | Documents / vectors |
| Volume mount covering `/app/data` | All of the above when co-located |

## Suggested cadence

- Daily snapshot of the data volume (or `pg_dump` for Postgres).
- Retain at least 7–30 days (legal/ops choice).
- Test restore on a staging host before launch.

## Restore outline

1. Stop the app.
2. Restore DB + JSON files (+ `plugin.key` if plugins used).
3. Confirm `DATABASE_URL` / store paths match.
4. Start app; check `/health` and login with a known account.

Account deletion does **not** purge backups — see `docs/ACCOUNT_DELETION.md`.
