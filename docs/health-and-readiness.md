# Health, readiness and build metadata

What to point a deployment platform at, what each endpoint means, and how
to read a failure. Added with issue #348, as a prerequisite for #321
(deploy the backend) and #322 (deploy `web/` against it).

## The three endpoints

| Endpoint | Question it answers | Touches Firestore | Can return 503 |
|---|---|---|---|
| `GET /api/v1/health/live` | Is the process running? | No | No |
| `GET /api/v1/health/ready` | Should this instance receive traffic? | Yes | Yes |
| `GET /api/v1/health/` | What exactly is wrong? | Yes | No |

### Which one to configure where

**Liveness probe → `/health/live`.** Nothing else. This endpoint
deliberately touches no dependency: if liveness depended on Firestore,
a database outage would fail the probe on every instance at once and the
orchestrator would restart-loop the entire fleet over something a restart
cannot fix.

**Readiness probe / load-balancer health check → `/health/ready`.** This
is the one that returns `503`, and the only one whose *status code* is
meaningful to a machine.

**Dashboards, uptime pages, a human debugging a deploy → `/health/`.**
Always `200`, because it exists to report the breakdown and a `503` would
hide the very detail being asked for. Read the body, not the code.

## Reading `/health/ready`

```json
{
  "status": "degraded",
  "ready": true,
  "checkedAt": "2026-08-04T14:21:03.118402+00:00",
  "components": [
    {"name": "firestore", "status": "ok",       "required": true,  "detail": "Connected.", "durationMs": 18.4},
    {"name": "auth",      "status": "ok",       "required": true,  "detail": "Signing key configured.", "durationMs": 0.01},
    {"name": "assistant", "status": "ok",       "required": false, "detail": "API key configured.", "durationMs": 0.01},
    {"name": "sms",       "status": "degraded", "required": false, "detail": "Twilio is not configured; SMS summaries are unavailable.", "durationMs": 0.01}
  ]
}
```

`ready` is the field to branch on. It is `false` only when a **required**
component is `down`.

A `degraded` *optional* dependency does not fail readiness. Taking an
instance out of rotation because Twilio is unconfigured would remove the
whole app in order to protect a feature most users never touch.

### Component statuses

- **`ok`** — working.
- **`degraded`** — this feature is unavailable, the rest of the app is not
  affected. Only ever applies to optional components.
- **`down`** — broken. On a required component, the instance is not ready.

### Which components are required

| Component | Required | What breaks without it |
|---|---|---|
| `firestore` | **yes** | Everything. Data is not persisted |
| `auth` | **yes** | No token can be issued or verified |
| `assistant` | no | `/assistant/chat` |
| `sms` | no | `/sms/send-summary` |

## The failure this was built for

`services/firestore_service.py` falls back to an in-memory
`MockFirestoreClient` when Firebase credentials are missing, logs a
warning, and carries on:

```
WARNING: Firebase credentials not found. Falling back to an in-memory mock Firestore database.
```

A deployment with a missing or malformed service account **starts
normally, serves traffic, accepts registrations and cycle logs, and loses
all of it on the next restart.** Nothing throws. The old `/health`
returned `{"status": "ok"}` throughout.

`/health/ready` now returns `503`:

```json
{
  "status": "down",
  "ready": false,
  "components": [
    {
      "name": "firestore",
      "status": "down",
      "required": true,
      "detail": "Running on the in-memory mock database. Firebase credentials are missing or unreadable; all data is lost on restart."
    }
  ]
}
```

Note that this is caught by an explicit type check, not by the read probe.
A read against the mock client succeeds perfectly — that is exactly why
the failure was invisible.

"Mocked" and "unreachable" are both `down` and both stop the instance
serving, but they need different fixes, so the `detail` strings
distinguish them. `detail` never contains a credential, a key fragment or
a project id.

The same picture is logged once at startup, so a misconfigured deploy is
visible in the first few log lines rather than only to whoever thinks to
curl the endpoint.

## Environment variables

### Required

| Variable | Notes |
|---|---|
| `JWT_SECRET` | `core/auth.py` raises at import if unset, so the process will not start |
| Firebase credentials | See `firestore_service.initialize_firebase()` |

### Optional features

| Variable | Enables |
|---|---|
| `GEMINI_API_KEY` | AI assistant |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` | SMS summaries — all three, or the send fails at request time |

A partially configured Twilio reports **which** variables are missing, so
that is a five-second fix rather than a read through the route's source.

### Build metadata

| Variable | Appears as |
|---|---|
| `APP_VERSION` | `build.version` (default `0.1.0`) |
| `GIT_COMMIT` or `VERCEL_GIT_COMMIT_SHA` | `build.commit`, truncated to 12 chars |
| `BUILD_TIME` | `build.builtAt` |
| `APP_ENV` | `build.environment` (default `development`) |

All fall back to `unknown` rather than failing, so a local run is not
noisy about metadata only CI can supply.

`/` reports `version` and `commit` from the same source. It previously
returned a hardcoded `"version": "0.1.0"` that had never changed, so after
a deploy there was no way to confirm which commit was live.

### Tuning

| Variable | Default | Notes |
|---|---|---|
| `HEALTH_CHECK_TIMEOUT` | `3.0` | Seconds any single dependency probe may take |

Every probe is individually timeout-bounded, so a wedged Firestore becomes
a fast `down` rather than a health endpoint that never answers — which
would escalate a degraded backend into an unresponsive one.

## Example platform configuration

Kubernetes:

```yaml
livenessProbe:
  httpGet: { path: /api/v1/health/live, port: 8000 }
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /api/v1/health/ready, port: 8000 }
  periodSeconds: 10
  failureThreshold: 3
```

Anything simpler (Render, Railway, Fly, a plain load balancer) wants
`/api/v1/health/ready` as its single health check path.

Keep the readiness poll interval above `HEALTH_CHECK_TIMEOUT`. A probe
slower than the interval that triggers it is a queue, not a check.
