# Edge / gateway rate limiting

## What NEXA has today (in-process)

| Limit | Scope | Implementation |
|-------|--------|----------------|
| `API_RATE_LIMIT_PER_MINUTE` | Per client IP, `/api/*` | `ApiRateLimitMiddleware` (single process) |
| Login IP / account | Auth login | `app.auth.rate_limit` |
| Register IP / hour | `REGISTER_RATE_LIMIT_PER_HOUR` | `register_ip_limiter` |

These counters **reset on restart** and **do not share** across multiple containers.
They are a last line of defense for a **single** instance, not distributed abuse protection.

**Do not** treat the in-memory middleware as a substitute for edge rate limiting.

## Deployment targets

| Target | Built-in edge rate limit? | Recommended approach |
|--------|---------------------------|----------------------|
| Docker + stock Caddy (`deploy/Caddyfile`) | **No** — stock Caddy has no rate_limit without a custom build / plugin | Put **Cloudflare** (or similar) in front, or terminate TLS on nginx/Caddy with a rate-limit module |
| Render Free / paid web service | Platform DDoS basics only; no per-route app limit in blueprint | Cloudflare proxy → Render, or accept single-instance middleware only for smoke |
| Railway + volume | Same as Docker | Cloudflare or nginx sidecar |
| Linux VPS | Operator-controlled | nginx `limit_req` or Caddy with rate-limit plugin in front of `:8080` |

## Suggested public v1 numbers (single instance + edge)

| Layer | Suggestion |
|-------|------------|
| Edge (Cloudflare / nginx) | ~60–120 req/min/IP for `/api/*`; tighter on `/api/v1/auth/login` and `/register` |
| App `API_RATE_LIMIT_PER_MINUTE` | `120` (already in `.env.production.example`) |
| `REGISTER_RATE_LIMIT_PER_HOUR` | `10` |
| Login limiters | Built-in (20/IP/min, 10/account/min) |

## Caddy note

The shipped `deploy/Caddyfile` only reverse-proxies. Adding `rate_limit` requires a
**non-standard** Caddy build (`xcaddy` + plugin). That is intentionally **not**
vendored here so the Docker image stays on distro Caddy. Use an external edge
or rebuild Caddy out-of-band if you need native Caddy limits.


## Public-cloud startup gate

`TRUSTED_EDGE_RATE_LIMIT_ENABLED=true` is now required by the durable-production / open-beta startup guard. This is an operator attestation, not automatic detection: set it only after the deployed CDN/WAF/reverse proxy has real distributed per-IP and route-specific limits, and has been tested from outside the host. The app continues to enforce its own in-process limits as a secondary layer. Setting the flag without configuring the edge does not create protection.
