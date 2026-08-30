Backend deployment guide
=========================

This document describes a minimal path to deploy the FastAPI backend to a managed host (Render or Railway).

Important: Do NOT commit production secrets. Use the platform's environment variables for keys and service account JSON.

Suggested steps (Render)
1. Create a new Web Service on Render (Private Service or Web Service).
2. Connect the repository and select the `main` branch.
3. Set the build and start commands:
   - Build command: `pip install -r backend/requirements.txt`
   - Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables on Render (Settings → Environment):
   - `JWT_SECRET` (required)
   - `FIREBASE_SERVICE_ACCOUNT_JSON` or `FIREBASE_SERVICE_ACCOUNT_PATH`
   - `GEMINI_API_KEY` (optional)
   - `ALLOWED_ORIGINS` (comma-separated production origins)
   - `TRUSTED_PROXY_IPS` (see **Trusted proxies** below — required for per-IP rate limiting to work)
   - Any `ASSISTANT_*` or `RATE_LIMIT_*` overrides you need
5. Configure health check (e.g., `GET /api/v1/health`) so the host restarts on failure.

Suggested steps (Railway)
1. Create a new project and link the repository branch.
2. Use the same build/start commands above.
3. Add the required environment variables via the Railway dashboard.
4. Configure deploy triggers and a health check endpoint.

Post-deploy
- Verify the service is reachable at the public URL provided by the host.
- Update `README.md` with the live backend URL and any platform-specific notes.

Trusted proxies
---------------

Several rate limits — reset-token guesses, email verification, registration,
provider registration, token refresh, the chat webhooks — are keyed on the
caller's IP address and have no second key, so getting that address right is
the difference between a working limit and no limit at all.

Behind a managed host the request the app sees comes from the platform's load
balancer. `request.client.host` is the balancer, and the caller's real address
is only in the `X-Forwarded-For` header. That header is written by the client
first and appended to by each proxy, so it is trustworthy exactly as far back
as the proxies you operate — and no further.

`TRUSTED_PROXY_IPS` is how the app is told where that chain ends.

| Value | Meaning |
|---|---|
| unset | Nothing is in front of this process. `X-Forwarded-For` is ignored entirely and the socket address is used. **This is the default**, and the right one for a local run. |
| `10.0.0.0/8, 172.16.0.0/12` | Addresses or CIDR blocks your proxies connect from. The header is read only when the request arrived from one of them. |
| `*` | Accept any peer as a proxy. For platforms that do not publish a stable egress range for their own balancer — Render, Cloud Run, a Vercel rewrite. Pair it with `TRUSTED_PROXY_HOPS`. |

`TRUSTED_PROXY_HOPS` (default `0`) is how many entries at the **right** of the
header your own infrastructure appends. One reverse proxy in front of the app
appends one entry, which then *is* the client, so `0` is correct. A CDN in
front of an ingress appends two, so the client is one further left and
`TRUSTED_PROXY_HOPS=1` skips the ingress's entry.

Whatever the configuration, the address taken is the right-most entry that is
not one of your own proxies. Entries to the left of it are client-supplied and
are discarded — a caller cannot pick their own rate-limit bucket by prepending
addresses.

Getting it wrong fails in one of two visible ways rather than silently:

- **Too narrow** (unset behind a balancer): every user shares one bucket and
  legitimate traffic starts seeing 429s. Fix by declaring the proxy.
- **Too wide** (`*` with the wrong hop count): the address logged and bucketed
  is an internal one, or one the client chose. Check what `X-Forwarded-For`
  your platform actually sends and count the entries it appends.

Security notes
- Never commit `FIREBASE_SERVICE_ACCOUNT_JSON` to the repo. Prefer a platform secret store.
- Use scoped `ALLOWED_ORIGINS` rather than `*` in production.
- Set `TRUSTED_PROXY_IPS` on any deployment behind a proxy. Without it the per-IP limits above bucket every caller together; with it set to `*` and no `TRUSTED_PROXY_HOPS` on a platform that appends more than one hop, they bucket on an internal address.

If you want, I can create a CI workflow snippet or a `render.yaml` example in a branch for review.
