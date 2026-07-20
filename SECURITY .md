# Security Policy

Rhythma handles sensitive personal health data — menstrual cycle logs, symptoms, mood, and other information users may consider private. We take security seriously and appreciate the community's help in keeping the project and its users safe.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.** Public issues are visible to everyone, including anyone who might exploit the report before a fix ships.

Instead, report privately by emailing:

**rhythma.official@gmail.com**

If GitHub Security Advisories are enabled for this repository, maintainers may coordinate fixes and publish advisories through GitHub after patches are available.

Please include (as much of this as you can):

- A clear description of the vulnerability and its potential impact
- Steps to reproduce it, including affected endpoint(s), screen(s), or file(s)
- The component involved — `backend/`, `rhythma_flutter/`, `web/`, or `landing-page/`
- Proof-of-concept code, request/response examples, or screenshots, if applicable
- Whether you believe the issue is currently being exploited
- Your contact information, so we can follow up with questions or credit you (if you'd like credit)

### What to expect

- **Acknowledgment:** We aim to confirm receipt of your report within **72 hours**.
- **Initial assessment:** We aim to give an initial severity assessment and next steps within **7 days**.
- **Fix timeline:** Depends on severity and complexity — critical issues (e.g., auth bypass, data exposure) are prioritized immediately; lower-severity issues are scheduled into regular development.
- **Disclosure:** We request coordinated disclosure. Please avoid publishing technical details until we've had a reasonable opportunity to investigate and release a fix. Once resolved, we're happy to coordinate a public disclosure and credit the reporter (if desired).

Severity is assessed using factors such as:

- Authentication bypass
- Unauthorized access to user data
- Remote code execution
- Sensitive information disclosure
- Privilege escalation
  
This is a community open-source project without a dedicated security team or a bug bounty program — we ask for your patience, and we'll be transparent about progress on your report.

If a vulnerability originates from a third-party dependency, fixes may depend on upstream maintainers releasing a patched version.

## Supported Versions

Rhythma does not currently use version tags or maintain multiple release branches. Only the latest code on `main` is supported with security fixes. There is no backport policy at this time.

| Version | Supported |
| --- | --- |
| `main` | ✅ |
| Any fork or older commit | ❌ |

## Scope

The following are in scope for security reports:

- **Backend (`backend/`)** — authentication and authorization (JWT issuance/verification, password hashing), Firestore data access rules and query construction, input validation on any endpoint, CORS configuration, secrets/credential handling, rate limiting (or lack thereof) on sensitive endpoints, and the AI assistant integration (prompt injection that leaks other users' data or bypasses auth, not just "the AI said something odd").
- **Mobile app (`rhythma_flutter/`)** — local data storage and encryption (Hive, `flutter_secure_storage`), handling of auth tokens on-device, any data leakage via logs, and insecure handling of the Gemini API key or backend credentials bundled with the app.
- **Web app (`web/`)** — auth token storage and handling in the browser, XSS/CSRF exposure, and any endpoint the web client calls insecurely.
- **Landing page (`landing-page/`)** — generally low sensitivity (no user data or auth), but dependency vulnerabilities or exposed secrets are still in scope.
- **Supply chain** — vulnerable dependencies in `requirements.txt`, `pubspec.yaml`, or any `package.json`, if you have evidence of a realistic exploit path (not just an automated scanner flag with no impact).

### Currently known, already-documented limitations

These are **known and already tracked** in the [README's Project Status](README.md#project-status) table — you don't need to report them again unless you've found a way to actually exploit them (in which case, please do report the specific exploit):

- Backend CORS origins are currently hardcoded to localhost for local development, with an explicit `TODO: Tighten this in production` in `backend/main.py`. This is a known gap that must be closed before any production deployment.
- Access tokens expire after 30 minutes with no refresh-token flow — by design for now, not a bug, but flagged here for awareness.
- The AI Assistant endpoint (`POST /assistant/chat`) has no per-user rate limiting yet.
- Encryption-at-rest for local Hive storage on the Flutter app has not yet been fully audited (the `encrypt` package is a dependency, but whether it's consistently applied to all sensitive Hive boxes hasn't been independently verified).

If you find a way to actually exploit one of these (e.g., a working CORS-based attack, not just "CORS is permissive"), please still report it — a demonstrated exploit is more actionable than a config observation.

### Out of scope

- Reports generated purely by automated vulnerability scanner findings that do not include a demonstrated exploit path or realistic security impact
- Social engineering, phishing, or physical attacks against maintainers or contributors
- Denial-of-service attacks requiring unrealistic traffic volume
- Issues in third-party services Rhythma depends on but doesn't control (Firebase, Gemini API, Twilio, Vercel) — please report those directly to the relevant vendor
- Best-practice suggestions with no security impact (these are welcome as a regular GitHub issue or PR instead, labeled `security` if relevant — see [CONTRIBUTING.md](CONTRIBUTING.md))

## For Contributors: Secure Development Practices

If you're contributing code, please review [CONTRIBUTING.md → Security Guidelines](CONTRIBUTING.md#security-guidelines) as well. In short:

- Never commit secrets, API keys, or credentials — use `.env.example` files as templates, never commit real `.env` files
- Validate and sanitize all user input on the backend, even if the Flutter or web client already validates it
- Use parameterized/typed Firestore queries — never build queries from unsanitized user input
- Don't log sensitive data (tokens, passwords, full health records) even at debug level
- When adding a new endpoint, explicitly state in your PR description whether it requires authentication (`Depends(get_current_user)`) and why
- If you're unsure whether something you found is a security issue worth a private report versus a normal bug, err on the side of reporting it privately first — we can always redirect it to a public issue together if it turns out not to be sensitive
- Prefer secure defaults (HTTPS, secure cookies where applicable, proper authorization checks, least-privilege access, and input validation).
  
## Data Handling Principles

Rhythma is built around a privacy-first principle: health data should stay on-device by default, with cloud sync as an explicit, opt-in choice. If you're implementing a feature that touches user health data, keep this principle in mind and flag in your PR if a design decision could weaken it (e.g., sending more data to the backend than a feature strictly needs).

If you accidentally commit credentials,
API keys, service account files, or other
sensitive material, notify a maintainer
immediately rather than only deleting the
commit. Repository history may also need
to be rewritten.

---

Thank you for helping keep Rhythma and its users safe. 💜 We greatly appreciate responsible security research and the time people invest in improving the safety of this project and its users.
