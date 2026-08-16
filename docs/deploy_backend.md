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

Security notes
- Never commit `FIREBASE_SERVICE_ACCOUNT_JSON` to the repo. Prefer a platform secret store.
- Use scoped `ALLOWED_ORIGINS` rather than `*` in production.

If you want, I can create a CI workflow snippet or a `render.yaml` example in a branch for review.
