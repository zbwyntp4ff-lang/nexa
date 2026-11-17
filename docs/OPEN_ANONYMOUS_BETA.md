# HEXA / NEXA anonymous public beta

This mode opens the existing chat UI without requiring an account. It does not
create a second model service and it does not expose provider credentials to
the browser.

## Runtime behavior

- The frontend skips the sign-in gate only when
  `NEXT_PUBLIC_NEXA_PUBLIC_BETA=true` is present at frontend build time.
- The backend accepts unauthenticated requests to the existing chat endpoints
  only when `NEXA_PUBLIC_BETA=true` is enabled.
- Anonymous requests are charged against a persistent IP-based allowance:
  **5 requests per rolling hour and 15 requests per UTC day**.
- Quota counters are stored in the shared SQL database in `guest_usage`.
  Clearing browser storage does not reset the counter.
- The browser displays the remaining daily allowance. The API returns HTTP
  429 and a `Retry-After` header when the allowance is exhausted.
- Other account-specific APIs remain protected by their existing auth rules.
- Conversation history for anonymous visitors remains in the browser's local
  chat store; it is not synced to a server account.

## Required deployment settings

Backend environment (server-side only):

```dotenv
NEXA_PUBLIC_BETA=true
ENVIRONMENT=production
NEXA_STORAGE_MODE=persistent
TOKENS_ENFORCE=true
DATABASE_URL=postgresql://USER:PASS@HOST/DB?sslmode=require
AUTH_SINGLE_USER=false
AUTH_SKIP_EMAIL_VERIFICATION=false
AUTH_COOKIE_SECURE=true
CORS_ALLOWED_ORIGINS=https://YOUR_DOMAIN
AUTH_PUBLIC_BASE_URL=https://YOUR_DOMAIN
```

Use the remaining required production settings from
`.env.production.example`, including a real provider API key, email delivery,
and durable storage. Never put provider keys in a `NEXT_PUBLIC_*` variable.

Frontend build environment:

```dotenv
NEXT_PUBLIC_NEXA_PUBLIC_BETA=true
NEXT_PUBLIC_API_BASE_URL=
```

Build the frontend again after changing `NEXT_PUBLIC_NEXA_PUBLIC_BETA`; Next.js
bakes public environment variables into the browser bundle.

## Operational notes

- Use one persistent Postgres database shared by all API instances. SQLite is
  suitable for a single-instance beta with a durable volume.
- The quota is keyed by the client IP observed by the API. Visitors behind the
  same public IP (for example, a school, office, or mobile carrier NAT) share
  the allowance. Configure trusted proxy handling at the hosting layer and
  never trust arbitrary client-supplied forwarding headers.
- Add edge-level bot protection / rate limiting at the CDN or reverse proxy.
  The application-wide API limiter remains an additional safety layer.
- Monitor provider spend. The anonymous quota limits chat requests; it does
  not itself cap provider-specific token cost or other non-chat endpoints.
- To close the public beta, set `NEXA_PUBLIC_BETA=false` on the backend and
  rebuild the frontend without `NEXT_PUBLIC_NEXA_PUBLIC_BETA`.
