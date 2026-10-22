[![Rhythma logo](https://github.com/ishita2740/Rhythma/raw/main/landing-page/public/logo1.png)](/ishita2740/Rhythma/blob/main/landing-page/public/logo1.png)

# Rhythma 🌸

*Her Rhythm. Her Health. Her Power.*

**A multilingual, offline-first, AI-powered menstrual & women's health companion — built from the ground up for Indian women.**

[![Flutter](https://img.shields.io/badge/Flutter-3.x-blue?logo=flutter)](https://flutter.dev) [![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)](https://fastapi.tiangolo.com) [![Gemini API](https://img.shields.io/badge/Gemini-API-orange?logo=google)](https://ai.google.dev) [![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](https://github.com/ishita2740/Rhythma/blob/main/LICENSE) [![Status](https://img.shields.io/badge/Status-Active%20Development-yellow)](#project-status)[![NSoC](https://img.shields.io/badge/Nexus%20Spring%20of%20Code-Participating-blueviolet)](#nexus-spring-of-code)

---

## Table of Contents

- [The Problem](#-the-problem)
- [What Rhythma Does](#-what-rhythma-does)
- [Platforms](#platforms)
- [Who Rhythma Is For](#who-rhythma-is-for)
- [Screenshots](#screenshots)
- [Demo Video](#demo-video)
- [Live Demo](#live-demo)
- [How Rhythma Compares](#-how-rhythma-compares)
- [Key Features](#-key-features)
- [Detailed Technology Stack](#️-detailed-technology-stack)
- [Project Status](#project-status)
- [Folder Structure](#folder-structure)
- [Configuration](#configuration)
- [Future Features](#future-features)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)
- [Disclaimer](#disclaimer)

---

## 🎯 The Problem

**1 in 5 Indian women** experience PCOD/PCOS symptoms, and national studies show a **19.6% PCOS prevalence** using Rotterdam criteria — yet most cases go unnoticed for years. Women in Tier-2, Tier-3, and semi-urban India face a compounding set of barriers:

- Popular period-tracking apps (Flo, Clue) assume 28-day cycles, English fluency, and stable internet
- Gynecologist access remains limited outside major cities
- Deep social stigma discourages open conversations about reproductive health
- Only **26%** of Indian women have regular mobile internet access
- No AI tool built natively for Indian languages, realities, and connectivity constraints

> *"Women's healthcare is not inaccessible because solutions don't exist. It is inaccessible because current solutions are not designed around Indian realities."*

**Rhythma is built from the ground up for Indian women — not adapted from a solution built for another market.**

---

## ✨ What Rhythma Does

Rhythma helps women **understand, track, and act** on their health privately, in their own language. Users log cycles, symptoms, mood, sleep, and lifestyle habits; Rhythma turns that data into personalized health insights instead of just raw charts.

Rhythma aims to be an offline-first, multilingual women's health companion for tier-2 and tier-3 Indian cities — supporting cycle tracking, an AI health assistant, and personalized wellness scoring in regional languages.

---

## Platforms

Rhythma consists of **two front ends sharing one backend**, not two separate products:

1. **Flutter mobile app** (`rhythma_flutter/`) — the primary experience today. Most of the UI described in this README lives here.
2. **Website** (`web/`) — a browser-based client aiming for **the same features as the app** (cycle tracking, AI Assistant, Insights, Profile), talking to the same FastAPI backend, for women who don't have or don't want to install a mobile app.
This is separate from `landing-page/`, a Next.js **marketing** site that explains the product but runs none of its functionality. Don't confuse the two when navigating the codebase.

---

## Who Rhythma Is For

Rhythma is designed to grow into support for multiple groups of Indian women, each with different needs. Not all of these are served by the app yet — this is the target scope, not a claim about current functionality.

| Group | Age / context | What they need |
| --- | --- | --- |
| **Teen girls (first period journey)** | 12–17 | Simple, non-clinical first-period guidance and menstrual education |
| **College students & working women** | 18–35 | Irregular-cycle tracking, PCOD/PCOS awareness, hormonal health support — **primary users of the current app** |
| **Women with irregular cycles** | 18–35+ | Long-term cycle consistency trends, not single-cycle guesswork |
| **Community / self-help groups** | Extended ecosystem (NGOs, rural users, shared devices) across Tier-2, Tier-3 & semi-urban India | Offline access, SMS support, and eventually WhatsApp-based access without needing to install an app |

| **Feature** | **Details** |
| --- | --- |
| **Languages** | 17 Indian languages plus English (translation files in `rhythma_flutter/lib/l10n/`) |
| **Cycle Metrics** | Factual cycle statistics (averages, shortest/longest cycles) and consistency trends |
| **Connectivity** | Offline-first; core features work with zero internet, sync when available |
| **Privacy** | Data stored encrypted on-device by default; cloud sync is opt-in |

Contributors working on onboarding flows, content, or accessibility should keep these different personas in mind, especially the gap between the adult-focused experience and the teen-focused one.

---

## Screenshots

*(Screenshots below reflect UI mockups)*

| Dashboard | Cycle Calendar | AI Assistant |
| --- | --- | --- |
| [![Dashboard](https://github.com/ishita2740/Rhythma/raw/main/screenshots/dashboard.png)](/ishita2740/Rhythma/blob/main/screenshots/dashboard.png) | [![Calendar](https://github.com/ishita2740/Rhythma/raw/main/screenshots/calender.png)](/ishita2740/Rhythma/blob/main/screenshots/calender.png) | [![AI Assistant](https://github.com/ishita2740/Rhythma/raw/main/screenshots/AI_assistant.png)](/ishita2740/Rhythma/blob/main/screenshots/AI_assistant.png) |

| Health Insights | SMS Summary |
| --- | --- |
| [![Health Insights](https://github.com/ishita2740/Rhythma/raw/main/screenshots/Health_Insights.png)](/ishita2740/Rhythma/blob/main/screenshots/Health_Insights.png) | [![SMS](https://github.com/ishita2740/Rhythma/raw/main/screenshots/SMS.png)](/ishita2740/Rhythma/blob/main/screenshots/SMS.png) |

---

## Demo Video

Two UI walkthroughs (mockups) are included in the repo under [`design-concepts/`](design-concepts):
- [`UI_Demo_1.mp4`](design-concepts/UI_Demo_1.mp4)
- [`UI_Demo_2.mp4`](design-concepts/UI_Demo_2.mp4)

---

## Live Demo

The public landing page is live at **[rhythma-navy.vercel.app](https://rhythma-navy.vercel.app)**. (This is the marketing site, not the app itself.)

---

## 🆚 How Rhythma Compares

| Feature | Flo | SheBloom | HerMantra | **Rhythma** |
|---|:---:|:---:|:---:|:---:|
| PCOS/PCOD Support | ✅ | ✅ | ✅ | ✅ |
| AI Early Risk Detection | ✅ | ➖ | ➖ | ✅ |
| Offline Functionality | ❌ | ✅ | ➖ | ✅ |
| SMS-Based Health Support | ❌ | ❌ | ❌ | ✅ |
| Privacy-First Data Ownership | ✅ | ✅ | ➖ | ✅ |
| Indian Language Support | ❌ | ✅ | ✅ | ✅ |
| Cycle Consistency Analysis (Factual) | ❌ | ❌ | ❌ | ✅ |
| Personalized Trend Insights (Factual) | ❌ | ❌ | ❌ | ✅ |
| Educational Ayurvedic Layer | ❌ | ➖ | ✅ | ✅ |

*Feature comparison based on publicly available information from official websites, app stores, and product documentation. Availability may change over time.*

**Key insight:** Existing platforms solve specific problems. Rhythma combines multiple underserved needs into one India-first ecosystem.

---

## 🚀 Key Features
 
| Feature                              | Status | Description                                                                              |
| ------------------------------------ | ------ | ----------------------------------------------------------------------------------------- |
| 🌸 Smart Cycle Tracking               | ✅     | Handles irregular cycles, no fixed 28-day assumption. Flow, mood, and symptom logging.   |
| 🤖 Gemini-Powered AI Assistant        | ✅     | Real `google-generativeai` integration (`gemini-2.5-flash`), gated behind rate limits.   |
| 📊 Cycle Variability Index (CVI)      | ✅     | Trained XGBoost model shipped in-repo, with a documented heuristic fallback.             |
| ❤️ Menstrual Health Score (MHS)      | 🟡     | Live today as a hand-written weighted average (CVI + sleep + stress + symptoms + lifestyle). The planned Logistic Regression ensemble is not built yet, and the lifestyle component silently falls back to a default score until profile fields land (#112). |
| 🏥 Hormonal Risk Indicator            | ✅     | 3-tier (Low/Medium/High) alerting derived from CVI.                                       |
| 📱 Offline-First Architecture         | ✅     | Hive local storage, Firestore sync, a sync-status indicator, and automatic replay of queued writes on reconnect (`flushPendingQueue`). |
| 🔒 Privacy-First Design               | ✅     | Auth, password policy, rate limiting, and a dedicated data-privacy/export service are implemented server-side. |
| 🌍 Indian Regional Languages          | ✅     | 17 languages have valid `.arb` translation files plus English. Translation completeness varies by language. |
| 📩 SMS Health Summaries               | ✅     | Real Twilio `Client` integration, gated on optional env credentials.                     |
| 🌿 Ayurvedic Correlation Layer        | ✅     | Educational wellness content layer merged (PR #436).                                     |
| 💬 WhatsApp / Telegram Bot            | ✅     | Full chat-linking + command engine (`status`, `link`, `unlink`, `help`) implemented — well ahead of the old roadmap's "Phase 4" label. |
| 🩺 Provider Portal                    | ✅     | Provider registration/login, patient consent, access logs, and patient list endpoints are implemented server-side — most of the old "Phase 5" scope. |
| 📄 PDF Health Report Export           | ✅     | Implemented client-side in Flutter via `pdf`/`printing`.                                 |
| 🌐 Web Application                    | ✅     | Vite + React + TypeScript app with auth, cycle tracking, AI Assistant, Insights, Profile, SMS, data-privacy and provider pages, a test suite, and CI (`web.yml`). |
 
---
> **Privacy:** Cycle data is stored on-device (encrypted Hive) by default and only syncs to the cloud if the user enables cloud sync. CVI/MHS scoring and the AI assistant run on the backend.

---

## 🛠️ Detailed Technology Stack

### Mobile — `rhythma_flutter/`
| Package | Version | Purpose | Status in code |
|---|---|---|---|
| flutter (SDK) | — | Core framework | — |
| dio | ^5.4.3 | HTTP client | Used in `api_client.dart`, `auth_service.dart` |
| http | ^1.2.2 | Secondary HTTP client | Present |
| flutter_secure_storage | ^9.2.2 | Secure token storage | Used in `secure_storage.dart` |
| provider | ^6.1.2 | State management | Used across `providers/` |
| google_fonts | ^6.2.1 | Typography | Used in theme |
| go_router | ^13.2.0 | Navigation | Used |
| hive / hive_flutter | ^2.2.3 / ^1.1.0 | Local offline storage | Used extensively in `local_storage_service.dart` |
| firebase_core / cloud_firestore / firebase_auth | ^3.3.0 / ^5.2.1 / ^5.1.3 | Cloud sync | Initialized in `main.dart` (`Firebase.initializeApp()`) and wired to `FirestoreService` for client-side offline-first sync — see [Flutter Client Firebase Setup](#flutter-client-firebase-setup-client-side-firestore-sync) |
| encrypt | ^5.0.3 | Local encryption | Present |
| fl_chart | ^0.68.0 | Charts | Used in `components/charts.dart` |
| flutter_localizations / intl | — / ^0.20.2 | i18n | Used, 17 languages generated |
| permission_handler | ^12.0.3 | Runtime permissions | Used by notification service |
| connectivity_plus | ^6.0.3 | Network state | Used in `firestore_service.dart` to detect connectivity and auto-trigger sync on restore |
| shared_preferences | ^2.3.2 | Lightweight key-value storage | Present |
| url_launcher | ^6.3.0 | Open external links | Present |
| flutter_local_notifications / timezone | ^22.0.1 / ^0.11.1 | Local notifications | Used for period-prediction and logging reminders, plus Settings toggles |
| email_validator | ^3.0.0 | Form validation | Present |
| flutter_lints | ^4.0.0 (dev) | Linting | Used in CI |

### Backend — `backend/` (`requirements.txt`)
Dependencies use minimum-version floors (`>=`), not exact pins.

| Package | Minimum version | Purpose |
|---|---|---|
| fastapi | 0.115 | Web framework |
| uvicorn[standard] | 0.30 | ASGI server |
| pydantic / pydantic-settings | 2.9 / 2.5 | Validation |
| firebase-admin | 6.6 | Server-side Firestore access |
| google-generativeai | 0.8.3 | Gemini API (model: `models/gemini-2.5-flash`, hardcoded in `assistant.py`) |
| google-api-core / grpcio / protobuf | 2.20 / 1.66 / 5.28 | Firestore errors; bounded to keep pip resolution shallow |
| xgboost | 2.1 | CVI scoring model |
| scikit-learn | 1.5 | ML utilities |
| numpy / pandas / joblib | 1.26 / 2.2 / 1.4 | Data handling / model I/O |
| twilio | 9.3 | SMS delivery — real integration in `sms.py` |
| python-jose[cryptography] | 3.3 | JWT |
| passlib[bcrypt] / bcrypt | 1.7.4 / 4.2 | Password hashing |
| httpx | 0.27 | Async HTTP client |
| python-dotenv | 1.0 | Env config |
| loguru | 0.7 | Logging |
| pytest / pytest-asyncio | 8.3 / 0.24 | Testing (54 test files) |

### Web App — `web/` (React, separate from landing page)
React 19.2, Vite 8, TypeScript 6, react-router-dom 7, i18next + react-i18next + browser language detector, axios. No UI component library, no chart library yet.

### Landing Page — `landing-page/` (Next.js, separate app)
Next.js 16, React 19, Tailwind CSS 4, shadcn/ui, class-variance-authority, lucide-react, @vercel/analytics. Deployed at `rhythma-navy.vercel.app`.

### CI/CD — `.github/workflows/`
GitHub Actions is configured for **backend** (`pytest`), **Flutter** (`flutter analyze` + `flutter test`), **web** (`web.yml`) and **landing page** (`landing-page.yml`), all path-filtered.

---

## ⚠️ Known Issues (verified against current code)

- **MHS is not yet ML-based**: despite the original "Logistic Regression" description, it currently runs as a documented hand-written weighted average, with the lifestyle sub-score defaulting to a flat 70.0 until profile fields ship (#112).
- **Landing page "Get Started" button** has an empty `href` and goes nowhere.

---

## Project Status

Legend: ✅ **Done** (real, working, verified against source) · 🟡 **Partial** (real code exists but incomplete, has a hardcoded piece, or is disconnected) · ❌ **Not implemented** (stub, placeholder, or absent)
 
*Every row below was checked directly against the current `backend/`, `rhythma_flutter/`, `web/`, and `landing-page/` source — not inferred from issue titles or an older status table.*
 
### Backend (FastAPI)
 
| Item | Status | Notes |
|---|---|---|
| Auth: register / login / JWT / rate limiting | ✅ | `core/auth_router.py` — bcrypt hashing, rate-limited |
| Auth: refresh tokens / forgot-password / reset-password / email verification | ✅ | All five routes are live in `auth_router.py` (`/refresh`, `/forgot-password`, `/reset-password`, `/verify-email`, `/resend-verification`) |
| Cycle logging (`POST /cycle/log`, history) | ✅ | Real Firestore persistence |
| Quick-log (single-field upsert for Home screen tiles) | ✅ | Merged into the same log endpoint — partial payloads merge without overwriting other fields for that day |
| Dashboard (`GET /dashboard`) | ✅ | Real stats from logged data |
| Insights / scores (`GET /insights/scores`) | ✅ | Calls the shared scoring service, which itself calls the CVI and MHS models — **these are exposed to the client**, not backend-only research code |
| CVI model | ✅ | Trained XGBoost model shipped (`cvi_model.joblib`), heuristic fallback if the file is missing |
| MHS model | 🟡 | Hand-written weighted composite, not the planned Logistic Regression ensemble; lifestyle sub-score defaults to a flat 70.0 until profile fields land (#112) |
| AI Assistant (`POST /assistant/chat`) | 🟡 | Real Gemini call, real system prompt; conversation history is persisted in Firestore (client-sent history is only a fallback). Not grounded in a sourced medical dataset |
| SMS (`api/sms.py`) | ✅ | Real Twilio client, real rate limiting and phone validation |
| WhatsApp/Telegram bot | ✅ | `api/bot.py` (280 lines) + `services/chatbot_service.py` (246 lines) — full webhook handling, chat-linking, and a command engine (`status`, `link`, `unlink`, `help`) |
| Provider portal | ✅ | Register/login, consent grant/list/revoke, access log, patient list/detail |
| Health check endpoint | ✅ | Wired into `main.py`, distinguishes mock-mode from real Firestore |
| CORS config | 🟡 | Configurable via `ALLOWED_ORIGINS` env var, sane localhost defaults for dev — worth confirming this is actually set for prod deploys |
| Backend test coverage | ✅ | 54 test files across auth, cycle, dashboard, insights, CVI/MHS, SMS, bot, provider, privacy |
| API documentation (OpenAPI descriptions) | 🟡 | `/docs` auto-generates; several routes still lack full descriptions/response models (#245) |
 
### Mobile (Flutter)
 
| Item | Status | Notes |
|---|---|---|
| Core screens (Home, Cycle, Assistant, Insights, Profile, Settings, SMS, Onboarding, Auth) | ✅ | All present and routed |
| Auth service | ✅ | Real `dio` calls to backend `/auth/*` |
| Local storage (Hive) | ✅ | `local_storage_service.dart` |
| Encryption at rest | ✅ | Hive boxes are opened with `HiveAesCipher`, not just listed as a dependency |
| Firestore sync | ✅ | Offline-first via Hive, syncs when online |
| Sync status indicator | ✅ | `SyncStatusProvider` — synced/syncing/pending/offline/error |
| Automatic reconnect-and-retry queue | ✅ | Pending writes are queued in Hive and flushed when connectivity returns |
| Cycle phase calculation | ✅ | `phaseKey()` and `phase()` both use the user's actual cycle day and cycle length |
| Localization — 17 Indian languages + English | ✅ | All 17 `.arb` files are valid JSON and generate localization classes |
| Widget/unit tests | ✅ | 31 test files |
| Local notifications | ✅ | `notification_service.dart` is wired to **both** period-prediction reminders and logging reminders, plus manual toggles in Settings |
| First-period / age-gated onboarding | ✅ | `screens/education/first_period_education_screen.dart` exists as a dedicated flow |
| Ayurvedic correlation content | ✅ | `lib/data/ayurveda_content.dart` — real content, merged via PR #436 |
| PDF report export | ✅ | `pw.Document` via `pdf`/`printing` |
 
### Web (`web/` — React + TS + Vite)
 
| Item | Status | Notes |
|---|---|---|
| App scaffold, routing, auth context | ✅ | `AuthContext.tsx`, protected routes |
| Login / Register pages | ✅ | Call the real backend |
| Home / Dashboard, Cycle, Assistant, Insights, Profile, Settings, SMS, Data Privacy, Sharing pages | ✅ | All exist with real implementations (100–489 lines each), not placeholders |
| Provider portal pages | ✅ | Login, register, dashboard, patient detail |
| i18n setup | ✅ | Configured |
| Test suite | ✅ | 39 test files, mocking at the API-client boundary and asserting on URL/payload |
| CI | ✅ | `.github/workflows/web.yml` exists |
 
### Landing Page (`landing-page/` — Next.js)
 
| Item | Status | Notes |
|---|---|---|
| Page, hero, features | ✅ | Live content |
| "Learn More" CTA | ✅ | Anchors to `#features`, works |
| "Get Started" CTA | ❌ | Renders as an `<a href="">` with an **empty href** — currently a dead link, not a missing-handler `<button>` |
| CI | ✅ | `.github/workflows/landing-page.yml` exists |
 
### Cross-cutting
 
| Item | Status |
|---|---|
| CI — backend, Flutter, web, landing-page | ✅ All four workflows exist in `.github/workflows/` |
| Architecture documentation | ✅ `docs/architecture.md` |
| Medical sourcing / disclaimers docs | ✅ `docs/medical_sources.md`, `docs/health-disclaimers.md` |

> This table is maintained by contributors alongside their PRs — see [CONTRIBUTING.md → Documentation Guidelines](CONTRIBUTING.md#documentation-guidelines). A PR that implements something listed here as ❌ or 🟡 should update the relevant row in the same PR.

---

## Folder Structure

```text
Rhythma/
├── backend/                              # FastAPI backend
│   ├── api/                              # Route modules
│   │   ├── assistant.py
│   │   ├── bot.py
│   │   ├── cycle.py
│   │   ├── dashboard.py
│   │   ├── health.py
│   │   ├── insights.py
│   │   ├── privacy.py
│   │   ├── provider.py
│   │   └── sms.py
│   ├── core/                             # Auth, middleware, security & validation
│   ├── data/                             # Medical reference datasets
│   ├── models/                           # CVI/MHS models & user model
│   ├── scripts/                          # Utility & training scripts
│   ├── services/                         # Business logic & AI services
│   ├── utils/                            # Shared helpers
│   ├── tests/                            # 54 backend test files
│   └── main.py                           # FastAPI entrypoint
│
├── rhythma_flutter/
│   ├── lib/ ...                          
│   └── test/                             # 31 test files
│
├── web/                                  
├── landing-page/                        
├── docs/                                 
├── .github/workflows/                    # backend, flutter, landing-page, web
├── design-concepts/
├── screenshots/
├── requirements.txt
├── LICENSE
└── README.md
```

## Installation

### Prerequisites

- Flutter SDK 3.x
- Python 3.10+
- Node.js 18+ (only if you're working on `web/` or `landing-page/`)
- Git
- A Firebase project (for backend user storage)
- A Gemini API key ([get one here](https://ai.google.dev))
- A Twilio account (optional — only needed for SMS)

```bash
git clone https://github.com/ishita2740/Rhythma.git
cd Rhythma
```

### Running Flutter

```bash
cd rhythma_flutter

# Platform folders are not committed — generate them first
flutter create .

flutter pub get

cp env.example .env
# Add GEMINI_API_KEY to .env to enable real AI responses
# (without it, the assistant falls back to a canned demo response)

# Add Firebase config files (see Firebase Setup below)
# android/app/google-services.json
# ios/Runner/GoogleService-Info.plist

flutter run
```

### Running Backend

```bash
cd backend

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r ../requirements.txt

cp .env.example .env
# Fill in JWT_SECRET, Firebase credentials, and (optionally) GEMINI_API_KEY / Twilio credentials

uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`, with interactive docs at `http://127.0.0.1:8000/docs`.

To run backend tests:

```bash
cd backend
pytest
```

### Running the Web App

```bash
cd web
cp .env.example .env.local
# VITE_API_BASE_URL defaults to http://localhost:8000/api/v1, adjust if needed

npm install
npm run dev
```

> **Note:** Both the Flutter app and the web app now require a real account. Register through either front end's Register screen against a running backend before you'll see anything past the login screen.

### Running the Landing Page

```bash
cd landing-page
npm install
npm run dev
```

---

## Configuration

### Environment Variables

**Backend (`backend/.env`)**

| Variable | Required | Purpose |
| --- | --- | --- |
| `JWT_SECRET` | Yes | Signs and verifies auth tokens. App will not start without it. |
| `FIREBASE_SERVICE_ACCOUNT_JSON` or `FIREBASE_SERVICE_ACCOUNT_PATH` | Yes (one of the two) | Firebase Admin SDK credentials for Firestore access |
| `GEMINI_API_KEY` | Optional | Enables the backend's `/assistant/chat` endpoint |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Optional | Enables the `/sms/send-summary` endpoint |
| `TRUSTED_PROXY_IPS` | Behind a proxy | Addresses or CIDR blocks the app's own load balancer connects from, or `*`. Unset means `X-Forwarded-For` is ignored and the socket address is used — safe, but it buckets every caller behind a balancer together, so the per-IP rate limits stop distinguishing users. See [docs/deploy_backend.md](docs/deploy_backend.md#trusted-proxies). |
| `TRUSTED_PROXY_HOPS` | Optional | How many `X-Forwarded-For` entries your own infrastructure appends. Defaults to `0`, correct for a single reverse proxy. |

**Flutter (`rhythma_flutter/.env`)**

| Variable | Required | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | Optional | Enables real AI responses in the Assistant tab; without it, a demo fallback response is shown |

**Web (`web/.env.local`)**

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | No — defaults to `http://localhost:8000/api/v1` | Backend base URL the web app calls for `/auth`, etc. Vite only exposes `VITE_`-prefixed vars to client code. |

The backend's CORS config already whitelists the Vite dev server (`http://localhost:5173`) alongside `localhost:8000`/`localhost:3000`, so a default local setup works without touching `main.py`.

### Firebase Setup

The backend currently uses Firebase **only for user accounts and cycle data** (via the Admin SDK). To set it up:

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com).
2. Generate a service account key: **Project Settings → Service Accounts → Generate new private key**.
3. Either paste the resulting JSON into `FIREBASE_SERVICE_ACCOUNT_JSON`, or save the file and point `FIREBASE_SERVICE_ACCOUNT_PATH` at it.
4. Ensure Firestore is enabled in the project (Native mode).

> **Note:** The steps above cover the **backend** Firebase credentials. The Flutter app separately initializes Firebase on the client side (`main.dart` calls `Firebase.initializeApp()` and `FirestoreService.init()`), so client-side sync also needs the platform config files below.

### Flutter Client Firebase Setup (Client-Side Firestore Sync)

For client-side offline-first Firestore synchronization (issue #27), the Flutter app needs its own Firebase config:

#### Android
1. In the Firebase Console, add an Android app with package name `com.example.rhythma`.
2. Download `google-services.json` and place it at:
   ```
   rhythma_flutter/android/app/google-services.json
   ```
3. `android/app/build.gradle.kts` and `android/settings.gradle.kts` are already configured with the google-services plugin.

#### iOS
1. In the Firebase Console, add an iOS app with bundle ID `com.example.rhythma`.
2. Download `GoogleService-Info.plist` and place it at:
   ```
   rhythma_flutter/ios/Runner/GoogleService-Info.plist
   ```
3. Add the file to the Xcode project if it is not already included.

#### App initialization
`main.dart` initializes Firebase and the sync service at startup:
```dart
await Firebase.initializeApp();
await FirestoreService.init();
```

This enables:
- Offline persistence via Firestore's local cache
- Automatic sync when connectivity is restored (issue #30)
- `SyncStatusProvider` for the sync status indicator (issue #20)
- Hive (local) remains the source of truth for reads; Firestore syncs when online and cloud sync is enabled

---

## Future Features

These are **not built yet**:

- **Regional language WhatsApp/Telegram expansion** — the bot's command engine exists (`status`, `link`, `unlink`, `help`); a full Gemini-powered conversational assistant over WhatsApp does not.
- **India regional health map** — an anonymized, aggregated PCOD/PCOS risk heatmap for public-health and NGO use.
- **ML-based MHS** — replacing the weighted-average score with the planned Logistic Regression ensemble (#112).

---

## Nexus Spring of Code

Rhythma is an official participating project in **Nexus Spring of Code (NSoC)**. NSoC contributors are welcome to pick up issues from the [Project Status](#project-status) tables, and should read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

---

## Contributing

Contributions are very welcome — code, docs, translations, design, and bug reports all matter.

Please read **[CONTRIBUTING.md](CONTRIBUTING.md)** before opening an issue or pull request. It covers project setup, branch naming, commit conventions, coding style, and the PR workflow in detail.

If you're looking for a place to start, the [Project Status](#project-status) tables above double as a task list: anything marked ❌ or 🟡 is fair game.

---

## License

This project is licensed under the MIT License. See [LICENSE](https://github.com/ishita2740/Rhythma/blob/main/LICENSE) for details.

---

## Acknowledgements

- Built by [Ishita Rathi](https://github.com/ishita2740)
- AI assistance powered by [Google Gemini](https://ai.google.dev)
- Backend framework by [FastAPI](https://fastapi.tiangolo.com)
- Mobile framework by [Flutter](https://flutter.dev)
- Read the origin story: [*Building Rhythma: An AI health companion for the women India's apps forgot*](https://medium.com/@rathiishita1005729/building-rhythma-an-ai-health-companion-for-the-women-indias-forgot-e249ac1cdc9a)
- [Live Demo](https://rhythma-navy.vercel.app)

---

## Disclaimer

Rhythma is intended for **educational and preventive health awareness** purposes only. It is not a certified medical device and does not provide medical diagnoses, prescriptions, or treatment recommendations. The cycle statistics and consistency observations provided by the application are for informational purposes only. The CVI and MHS scores are experimental indicators for awareness only and are not diagnostic. The Ayurvedic content is educational and non-prescriptive, not a substitute for medical advice. Always consult a qualified healthcare professional for medical advice.

---

*Built with 💜 by [Ishita Rathi](https://github.com/ishita2740) for the women India's apps forgot.*

#### *AI For Every Phase of Her Health.*
