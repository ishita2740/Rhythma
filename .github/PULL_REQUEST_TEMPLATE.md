## Thanks for contributing to Rhythma! Please fill this out completely — PRs with an empty or skipped template take longer to review.

#### See CONTRIBUTING.md for the full contribution guide.


## Description

What does this PR change, and why?



## Related Issue

Link the issue this closes or relates to. Non-trivial changes should have an issue first — see CONTRIBUTING.md → Issue Workflow. 

Closes #

## Component(s) Affected

- [ ] Backend (`backend/`)
- [ ] Mobile app (`rhythma_flutter/`)
- [ ] Web app (`web/`)
- [ ] Landing page (`landing-page/`)
- [ ] Docs only (README, CONTRIBUTING, architecture, etc.)
- [ ] CI / tooling

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactor (no behavior change)
- [ ] Tests
- [ ] Other:

## Testing Performed

List the commands you ran and what you checked manually. Be specific — "tested it" isn't enough for reviewers to trust the change.

- [ ] `flutter analyze`
- [ ] `dart format --output=none --set-exit-if-changed .`
- [ ] `flutter test`
- [ ] `pytest -v` (backend)
- [ ] `npm run lint` (web)
- [ ] `npm run build` (web)
- [ ] Manually exercised the endpoint/screen — describe what you checked:

e.g. "Registered a new user, confirmed 409 on duplicate email, confirmed JWT returned and valid for 30 min" 

**Edge cases considered:**

## Screenshots / Videos (required for any UI change)

Before/after screenshots, or a short recording for animations, gestures, or multi-step flows. 

- [ ] Not applicable — no UI change
- [ ] Included below

**Light mode:**

**Dark mode** *(Flutter only, if the change could render differently):*

**Non-English locale** *(if the screen has localized strings — confirms no overflow/truncation):*

## API Documentation (required for any new/changed backend endpoint)

Skip this section entirely if this PR doesn't touch backend/api/ 

- **Route & method:**
- **Request/response shape:**  (paste or link the Pydantic models)
- **Requires authentication?**  (Depends(get_current_user)? yes/no)
- **New environment variables:**  (required or optional; confirm .env.example is updated)
- **Error cases:**   (what status codes can this return, and why)

## Documentation Updates

- [ ] Not applicable
- [ ] Updated `README.md` (behavior/feature description)
- [ ] Updated the [Project Status](https://github.com/ishita2740/Rhythma/blob/main/README.md#project-status) table — **required if this PR moves an item from ❌/🟡 to a more complete state, or introduces a new gap**
- [ ] Updated `docs/architecture.md` (new data flow, dependency, or external service)
- [ ] Updated the relevant `.env.example` (new environment variable)
- [ ] Added new user-facing strings to `app_en.arb` (and ideally `hi`/`mr`/`ta`/`te`)

## Out of Scope

Anything you deliberately left out of this PR, and why (e.g. "backend sync not included — tracked separately in #27").

## Checklist

- [ ] I have read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] I rebased/merged the latest `main` into this branch
- [ ] I tested my changes locally (see Testing Performed above)
- [ ] Any behavior change includes a new or updated test
- [ ] I removed debug prints, commented-out dead code, and unused imports I introduced
- [ ] This PR is scoped to one logical change (see [Maximum Recommended PR Size](../CONTRIBUTING.md#maximum-recommended-pr-size))
- [ ] I did not commit any secrets, credentials, or real `.env` files
