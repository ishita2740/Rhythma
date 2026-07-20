# Contributing to Rhythma 🌸

Thank you for your interest in contributing to Rhythma — an open-source, multilingual women's health companion focused on accessibility, privacy and meaningful health insights, being built for women in India. Every contribution matters: code, documentation, translations, design, and bug reports.

Please read this guide before opening an issue or pull request.

---

## Table of Contents

- [Project Setup](#project-setup)
- [Feature Areas Open for Contribution](#feature-areas-open-for-contribution)
- [Branch Naming](#branch-naming)
- [Issue Workflow](#issue-workflow)
- [Issue Assignment Policy](#issue-assignment-policy)
- [Issue Labels](#issue-labels)
- [Coding Style](#coding-style)
  * [General](#general)
  * [Flutter](#flutter)
  * [Backend](#backend)
  * [Web](#web)
- [Commit Message Format](#commit-message-format)
- [Code Quality Requirements](#code-quality-requirements)
- [How to Test](#how-to-test)
- [Before Opening a PR](#before-opening-a-pr)
- [PR Workflow](#pr-workflow)
- [Maximum Recommended PR Size](#maximum-recommended-pr-size)
- [Required Screenshots/Videos for UI PRs](#required-screenshotsvideos-for-ui-prs)
- [Required API Documentation for Backend PRs](#required-api-documentation-for-backend-prs)
- [Security Guidelines](#security-guidelines)
- [Documentation Guidelines](#documentation-guidelines)
- [Review Expectations](#review-expectations)
- [Code of Conduct](#code-of-conduct)

---

## Project Setup

```
git clone https://github.com/ishita2740/Rhythma.git
cd Rhythma
```

**Flutter app:**

```
cd rhythma_flutter
flutter pub get
cp env.example .env     # add GEMINI_API_KEY if you want live AI responses
flutter run
```

Note: `android/`, `ios/`, and the other platform folders are already committed to the repo (only build artifacts inside them, like `android/.gradle/` or `ios/Pods/`, are gitignored). There's no need to run `flutter create .` — doing so can overwrite already-configured platform files (manifests, icons, permissions).

**Backend:**

```
cd backend
python -m venv venv && source venv/bin/activate
pip install -r ../requirements.txt
cp .env.example .env    # JWT_SECRET and Firebase credentials are required
uvicorn main:app --reload
```

**Web app:**

```
cd web
cp .env.example .env.local   # VITE_API_BASE_URL defaults to a local backend, adjust if needed
npm install
npm run dev
```

Note that the web app is an early scaffold — you'll get a working login/register flow and a placeholder home page, not the full feature set. See the README's [Platforms](https://github.com/ishita2740/Rhythma/blob/main/README.md#platforms) section for what exists there today.

Full setup details, environment variables, and Firebase configuration live in the [README](https://github.com/ishita2740/Rhythma/blob/main/README.md#installation) — not duplicating that here; keeping this file focused on the *contribution process*.

---

## Feature Areas Open for Contribution

The [README's Project Status](https://github.com/ishita2740/Rhythma/blob/main/README.md#project-status) table is the source of truth for what's implemented, in progress, or planned. A few areas are called out here because they're currently **clean-slate** — no code, UI, or content exists yet — and are good candidates for a contributor who wants to own something end-to-end rather than patch an existing flow.

**Before starting on any of these, open an issue first** (see [Issue Workflow](#issue-workflow)). Each one needs a scoping discussion, since the "right" first version is genuinely open, not just an implementation detail.

> **Highest-priority non-clean-slate gap:** the Cycle screen's daily-logging bottom sheet (`log_entry_sheet.dart`) already saves each entry via `LocalStorageService.saveCycleLog()` — that part works. The break is one layer up: `cycle_provider.dart`, which drives the calendar's "logged day" highlighting, uses a hardcoded mock `_loggedDays` set (literally commented `// Mock logged days`) instead of reading from `LocalStorageService.getCycleLogs()`. So a real log gets saved, but the calendar doesn't reflect it. Separately, nothing in the Flutter app calls the backend's working `POST /cycle/log` at all — all logging today is local-only (Hive), with no path to the backend or Firestore yet. Fixing `CycleProvider` to read real Hive data is a small, well-scoped, high-impact issue if you want one; wiring an actual backend sync call is a bigger, separate piece of work (related to the Firestore sync stub below).

- **First Period Guidance** — a dedicated onboarding and education flow for first-time users aged 12–17, with simpler language, a different tone, and content distinct from the general cycle-tracking experience. Open questions before code gets written: how do we determine a user is in this age group, how much of the existing navigation should this flow reuse vs. replace, and where does the educational content itself come from (needs review, ideally from someone with relevant health-education background).
- **Ayurvedic Correlation Layer** — educational content connecting lifestyle and cycle patterns to traditional Ayurvedic wellness concepts, surfaced contextually alongside cycle/insight data. This is content-heavy work as much as code: sourcing accurate, non-prescriptive material is the harder half of this feature, and it needs to stay clearly educational rather than reading as medical advice (see [Disclaimer](https://github.com/ishita2740/Rhythma/blob/main/README.md#disclaimer)).
- **WhatsApp Bot Integration** — a Gemini-powered WhatsApp assistant (via Twilio/Meta Cloud API) for cycle tracking and health Q&A without an app install. This one has a real dependency: it should build on the existing `backend/api/assistant.py` endpoint, which currently exists but isn't called by the Flutter app or the web app yet. If you're interested in this, check the README's [Project Status](https://github.com/ishita2740/Rhythma/blob/main/README.md#project-status) table first for the current state of the AI Assistant integration, since building against the wrong assumption means redoing the work later.
- **Website product pages** — `web/` now has a working login/register/protected-route scaffold (React + Vite + TypeScript), but cycle tracking, AI Assistant, and Insights pages don't exist yet — only a placeholder home page. Building these against the existing backend endpoints (the same ones the Flutter app calls) is open work, and it's reasonable to propose tackling one page at a time rather than all of it in one PR (see [Maximum Recommended PR Size](#maximum-recommended-pr-size)).

If you have an idea that isn't listed in the README's Future Features section at all, that's fine too — open an issue describing it and we can discuss whether and how it fits before any code is written.

---

## Branch Naming

Branch off `main` using one of these prefixes:

| Prefix | Use for |
| --- | --- |
| `feature/` | New functionality (`feature/cycle-log-persistence`) |
| `fix/` | Bug fixes (`fix/sms-rate-limit-reset`) |
| `docs/` | Documentation-only changes (`docs/firebase-setup`) |
| `refactor/` | Code restructuring with no behavior change (`refactor/auth-router-cleanup`) |
| `test/` | Adding or fixing tests (`test/cycle-endpoint-coverage`) |
| `chore/` | Tooling, dependencies, config (`chore/add-analysis-options`) |

Use lowercase, hyphen-separated, descriptive names — not issue numbers alone (`fix/123` tells a reviewer nothing).

---

## Issue Workflow

1. **Search first.** Check open and closed issues to avoid duplicates.
2. **Open an issue before starting non-trivial work.** Small typo fixes or one-line bug fixes can skip straight to a PR; anything that touches app behavior, data models, or more than a couple of files should have an issue first so the approach can be discussed. This applies especially to the clean-slate areas in [Feature Areas Open for Contribution](#feature-areas-open-for-contribution).
3. **Discuss the approach before implementing large features.**
4. **Wait for a maintainer acknowledgment** on larger issues before submitting a large PR against them — this avoids wasted effort if the direction needs to change.

---

## Issue Assignment Policy

- Comment on the issue with the implementation approach asking to be assigned before starting work, so two people don't duplicate effort.
- If an issue has been assigned but shows no activity or linked PR after **7 days**, it's fair game to ask the maintainer to reassign it.
- Don't open a PR for an issue assigned to someone else without coordinating with them first.
- Assigned issues may be reassigned if there is no visible activity for an extended period.
- Work on only one assigned issue at a time unless approved by a maintainer.
= Please wait until a maintainer assigns the issue before starting work.
- You're always welcome to reopen the discussion or submit a fresh PR later.
  
---

## Issue Labels

The repository uses labels to help contributors identify suitable issues.

| Label | Description |
| ------ | ----------- |
| `good first issue` | Beginner-friendly issues for first-time contributors. |
| `help wanted` | Community contributions are encouraged. |
| `bug` | Something isn't working as expected. |
| `enhancement` | New features or improvements. |
| `documentation` | Documentation updates and improvements. |
| `accessibility` | Accessibility and inclusive design improvements. |
| `localization` | Translation and multilingual improvements. |
| `backend` | Backend/API related tasks. |
| `mobile` | Flutter/mobile application tasks. |
| `content` | Educational or health-related content improvements. |
| `easy` | Suitable for beginners. |
| `medium` | Moderate complexity. |
| `hard` | Advanced tasks requiring deeper understanding. |
| `priority: high` | High priority issues. |
| `priority: medium` | Medium priority issues. |
| `priority: low` | Low priority issues. |
| `security` | Security-related improvements or fixes. |
| `ECSoC26` | Issues participating in Elite Summer of Code 2026. |

## Contribution Recognition

Some labels are used to recognize exceptional contributions during community programs.

| Label | Meaning |
|--------|---------|
| good-pr | High-quality pull request (+15 XP) |
| good-ui | Exceptional UI/Flutter contribution (+25 XP) |
| good-backend | Exceptional backend contribution (+50 XP) |

These labels are awarded by maintainers after review.
They are **not** requested by contributors.

---

## Architecture

Before implementing major features, spend some time understanding the existing architecture.

Avoid introducing duplicate services, providers, API layers, or utilities when similar functionality already exists.

---

## AI-assisted Contributions

AI tools (ChatGPT, Claude, GitHub Copilot, etc.) may be used to assist development.

However, contributors remain fully responsible for:

- Code correctness
- Testing
- Documentation
- Security
- Code quality

AI-generated code will be reviewed using the same standards as handwritten code.

---

## Coding Style

### General

- Keep code simple and maintainable.
- Prefer consistency over personal preference. Match the existing architecture and coding style unless a refactor has been discussed first.
- Avoid unnecessary dependencies.
- Prefer reusable components and services.
- Remove debug code before submitting.

### Flutter

- Use snake_case.dart file names.
- Use PascalCase for classes and widgets.
- Use localization for user-facing strings.
- Keep business logic out of UI widgets.
- Follow null-safety best practices.

### Backend

- Use type hints for new code.
- Use Pydantic models for request and response schemas.
- Use proper HTTP status codes.
- Keep route handlers lightweight.
- Move reusable logic into services.

### Web

- TypeScript, not plain JS — the project is set up with `tsc -b` as part of the build.
- Follow the existing `web/src/api/client.ts` pattern for backend calls (shared Axios instance, token interceptor) rather than creating ad-hoc `fetch`/`axios` calls per page.
- Use `react-i18next` for user-facing strings, mirroring the same locale set as Flutter (`en`, `hi`, `mr`, `ta`, `te`) — add new keys to `web/src/i18n/locales/en.json` at minimum.
- Keep new product pages (cycle tracking, Insights, Assistant) behind `ProtectedRoute`, consistent with the existing auth pages.
- Run `npm run lint` (oxlint) before opening a PR.

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short summary>

<optional body>

<optional footer, e.g. "Closes #42">
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Examples:**

```
feat(cycle): persist cycle logs to Hive on save

fix(sms): reset rate limiter window correctly after 60 seconds

docs(readme): correct cloud sync status to reflect stubbed implementation

test(backend): add coverage for /cycle history endpoint
```

Keep the summary line under ~72 characters, written in the imperative mood ("add", not "added" or "adds"). Squash fixup commits (`fix typo`, `address review comments`) before merge where possible.

---

## Code Quality Requirements

- **Any behavior change must include a test update or addition** — either a new test, or an update to an existing one if you changed the behavior it covers.
- **Contributors are responsible for verifying their changes locally before opening a pull request.**

---

## How to Test

**Flutter:**

```
cd rhythma_flutter
flutter analyze
dart format --output=none --set-exit-if-changed .
flutter test
```

**Backend:**

```
cd backend
pytest -v
```

**Web:**

```
cd web
npm run lint
npm run build   # tsc -b && vite build — catches type errors even without a dedicated test suite yet
```

There's no automated test suite in `web/` yet — if you're adding meaningful logic (not just markup), consider adding one rather than relying on manual checking.

If you added an endpoint, manually exercise it via the interactive docs at `http://127.0.0.1:8000/docs` (or `curl`/Postman) in addition to any automated tests, and describe what you checked in the PR description.

---

## Before Opening a PR

- [ ] Rebase or merge the latest `main` into your branch
- [ ] Run the full relevant test suite (Flutter and/or backend)
- [ ] Update documentation if you changed behavior (README, `docs/architecture.md`, or inline docstrings — see [Documentation Guidelines](#documentation-guidelines))
- [ ] Remove debug prints, commented-out dead code, and unused imports you introduced
- [ ] Confirm the PR is scoped to one logical change (see [Maximum Recommended PR Size](#maximum-recommended-pr-size))
- [ ] For UI changes, capture before/after screenshots or a short screen recording
- [ ] For anything that changes or introduces API behavior, update or add the relevant API documentation

---

## PR Workflow

1. **Open the PR against `main`**, with a descriptive title following the [commit message format](#commit-message-format) style (e.g., `feat(cycle): persist cycle logs to Hive`).
2. **Fill out the PR description** with:
   - **What** changed and **why**
   - **Testing performed** (commands run, manual steps taken, edge cases checked)
   - **Screenshots/videos** for any UI change
   - Linked issue(s), using `Closes #issue_number` where applicable
   - Anything intentionally left out of scope, and why
3. **Request review.** If you're not sure who should review, tag a maintainer or ask in the issue.
4. **Respond to review comments** in the PR thread rather than out-of-band, so the discussion stays with the code.
5. **Keep the PR up to date** with `main` if review takes a while and conflicts appear.
6. A maintainer will merge once the PR is approved and checks (where they exist) pass.

## Draft Pull Requests

If your work is still in progress, open the PR as a **Draft Pull Request**.

Draft PRs are encouraged for:

- Early feedback
- Architecture discussions
- Large features
- Collaborative development

Convert it to "Ready for Review" only after completing the checklist.

---

## Maximum Recommended PR Size

- **Split large features into multiple pull requests.** Each PR should focus on one logical change (one feature, one bug fix, or one refactor). If your work spans multiple areas, break it into smaller, reviewable PRs whenever possible.
- **Use multiple meaningful commits.** Organize your work into logical commits with clear commit messages instead of one large commit. This makes the review process easier and keeps the project history clean.

---

## Required Screenshots/Videos for UI PRs

Any PR that changes a Flutter screen's or web page's appearance or interaction must include:

- A **before/after screenshot** (or a screen recording for animations, gestures, or multi-step flows)
- Screenshots for **both light and dark mode** if the change could plausibly render differently between them (Flutter only — the web app doesn't have a dark mode yet)
- If the change affects a screen with existing localized strings, a screenshot in at least one non-English locale (e.g., Hindi) to confirm text doesn't overflow or truncate

Attach these directly in the PR description (drag-and-drop into the GitHub PR body works fine).

---

## Required API Documentation for Backend PRs

Any PR that adds or changes a backend endpoint must include, in the PR description:

- The **route, method, and request/response shape** (Pydantic models are usually sufficient — paste them or link to the file)
- Whether the endpoint requires authentication (`Depends(get_current_user)`)
- Any new environment variables it depends on (and whether they're required or optional — update `.env.example` accordingly)
- A note on error cases (what status codes it can return and why)

---

## Security Guidelines

Security is a priority.

Please:

- Never commit secrets or credentials
- Never commit .env files
- Use .env.example for configuration examples
- Remove sensitive logs before submission
- Report security issues privately to maintainers

If you discover a security vulnerability, please **do not open a public GitHub issue.**
Instead, contact the maintainers privately so the issue can be investigated before disclosure.

---

## Documentation Guidelines

- If your change alters **user-facing behavior**, update the relevant section of the [README](https://github.com/ishita2740/Rhythma/blob/main/README.md) in the same PR — particularly the [Project Status](https://github.com/ishita2740/Rhythma/blob/main/README.md#project-status) table, since it's the single source of truth for what's implemented vs. in progress. A PR that makes a feature work end-to-end but leaves it listed as "❌ Not implemented" in the README will be asked to update that table before merge.
- If your change alters the **system design** (new data flow, new dependency between the Flutter app and backend, new external service), update `docs/architecture.md` accordingly.
- If you add a **new environment variable**, update the corresponding `.env.example` file (`backend/.env.example`, `rhythma_flutter/env.example`, or `web/.env.example`) and the README's [Environment Variables](https://github.com/ishita2740/Rhythma/blob/main/README.md#environment-variables) table.
- If you add a **new user-facing string**, add it to `app_en.arb` at minimum; adding it to the other four locale files (`hi`, `mr`, `ta`, `te`) is strongly encouraged but won't block a PR if you leave a note asking for translation help.
- Documentation should describe **what the code currently does**, not the eventual vision for it. When in doubt, describe the current behavior and put aspirational notes clearly under a "Future Features" or "planned" heading.

---

## Review Expectations

- Reviewers will check for: correctness, code quality, scope (see [Maximum Recommended PR Size](#maximum-recommended-pr-size)), consistency with existing conventions, test coverage, and documentation updates.
- You may be asked to split a large PR into smaller ones — this isn't a rejection of the work, just a request to make it reviewable.
- Reviewers will point out places where a change silently reintroduces a gap this project is trying to close (e.g., adding a new hardcoded UI value instead of wiring it to real data, or adding a new dependency that isn't actually used yet, mirroring several unused dependencies already in the codebase). Please treat this feedback as part of the project's push toward accuracy between what's declared and what's implemented, not personal criticism.
- Maintainers reserve the right to close stale PRs (no activity for 7+ days after review feedback) — feel free to reopen or resubmit when you're able to continue.
- You may be asked to make revisions before a pull request is merged.

---

## Merge Policy

Maintainers may squash, rebase, or merge commits depending on what best preserves project history.

The merge strategy is chosen by the maintainers.

---

## Code of Conduct

This project is committed to providing a welcoming and respectful environment for all contributors, regardless of experience level, background, or identity. Please be kind, constructive, and considerate in all interactions — in issues, PRs, and reviews.

Harassment, discrimination, abusive behavior, or personal attacks will not be tolerated.

---

## Community

You're welcome to join our Discord community for general discussions, questions, brainstorming ideas, or getting help with the project.

**Discord:** https://discord.com/channels/1385270036331233371/1525165966382862626

Please use:
- **GitHub Issues** for bugs and feature requests.
- **GitHub Pull Requests** for code reviews.
- **Discord** for general discussions, questions, brainstorming, and community support.

Project decisions and accepted feature requests should always be documented on GitHub so they're easy for everyone to find later.

---

## Questions?

If you are unsure about implementation details, project direction, or issue scope, open an issue and ask before starting work — it's easier for everyone that way.

If you're unsure where to start:

- Look for `good first issue`
- Look for `help wanted`
- Read the README completely
  
We appreciate every contribution and thank you for helping improve Rhythma. 💜
