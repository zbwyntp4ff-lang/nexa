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


## Ready-to-adapt Nginx edge template

The repository now includes (the Nginx template uses the `http2 on` directive and targets Nginx 1.25.1+):
- `deploy/nginx-edge.conf.example` — TLS reverse proxy with a general API limit and stricter limits for login, registration, password recovery, email verification, device login and passkey login.
- `deploy/nginx-proxy-headers.conf.example` — forwarded headers for the upstream NEXA Caddy container.

This is a **template, not an active deployment**. Before use:

1. Put NEXA Caddy behind Nginx and publish only Nginx's HTTPS port. Bind the Docker port to loopback, e.g. `127.0.0.1:8080:8080`; do not expose the Caddy container port publicly.
2. Copy `nginx-proxy-headers.conf.example` to `/etc/nginx/snippets/nexa-proxy-headers.conf`.
3. Replace `nexa.example.com` and the certificate paths in `nginx-edge.conf.example`.
4. Include the edge config from the Nginx `http` context. The `limit_req_zone` directives must remain in the `http` context.
5. If Cloudflare is in front, first configure Nginx Real IP using **only** Cloudflare's currently published IPv4/IPv6 ranges and `CF-Connecting-IP`. Do not trust forwarded client-IP headers from arbitrary sources. Without that allow-list, all requests may appear to come from Cloudflare and share one limit bucket.
6. Run `nginx -t`, reload Nginx, then test 429 responses from separate client IPs and verify the application receives the expected scheme/host.

The sample thresholds are conservative starting points, not load-tested production values. Tune them after observing legitimate traffic and AI/SSE request patterns. This config does not enable multi-worker support: keep one NEXA API process and one app instance until shared transactional storage and distributed queues/limits exist.


### Caddy → Uvicorn client IP trust (required)

Nginx limits requests by its real client address, but NEXA also has in-process
API/auth limiters that use the ASGI client address. When Nginx proxies to Caddy,
Caddy must trust **only the exact Nginx source IP** so its normalized
`X-Forwarded-For` reaches Uvicorn. Otherwise every user can appear to the app
as the same proxy and share one in-process rate-limit bucket.

Add the following to the global options at the top of `deploy/Caddyfile`, after
replacing the placeholder with the address Caddy actually sees for Nginx (often
the Docker bridge gateway when Nginx runs on the host):

```caddyfile
{
    servers {
        trusted_proxies static <NGINX_SOURCE_IP>/32
        trusted_proxies_strict
    }
}
```

Use `/128` for one IPv6 address. Do not copy the placeholder literally. Avoid
`private_ranges` unless the proxy network is isolated and only trusted proxies
can connect to Caddy. If Cloudflare is in front of Nginx, configure Nginx Real IP
from Cloudflare's official ranges first; Caddy should trust the Nginx hop, not
arbitrary client-supplied forwarding headers.
