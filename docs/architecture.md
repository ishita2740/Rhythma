# Rhythma — System Architecture

## Overview

Rhythma follows an **offline-first, privacy-first** architecture designed for low-connectivity environments in tier-2 and tier-3 India.

```
┌────────────────────────────────────────────────────────────────┐
│                        Flutter App                             │
│                                                                │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌─────────────┐    │
│  │   Home   │  │  Cycle   │  │ Assistant │  │  Insights   │    │
│  └──────────┘  └──────────┘  └───────────┘  └─────────────┘    │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Hive (Local Storage) ← AES-256 encrypted               │    │
│  └──────────────────────────┬────────────────────────────┘    │
│                             │ sync (when online)               │
└─────────────────────────────┼──────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   FastAPI Backend   │
                    │                    │
                    │ /auth      ──► JWT / Firebase Auth
                    │ /assistant ──► Gemini API
                    │ /cycle     ──► Firestore
                    │ /insights  ──► XGBoost + LR models
                    │ /sms       ──► Twilio
                    └─────────▲──────────┘
                              │ API requests (HTTP / Cookie auth)
┌─────────────────────────────┴──────────────────────────────────┐
│                     React Web Client (web/)                    │
│                                                                │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌─────────────┐    │
│  │   Home   │  │  Cycle   │  │ Assistant │  │  Insights   │    │
│  └──────────┘  └──────────┘  └───────────┘  └─────────────┘    │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Local Storage (Auth / Session State Cache)             │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Offline Mode
1. User logs cycle data / symptoms → stored in Hive (encrypted locally)
2. CVI / MHS scores computed on-device
3. AI assistant queries cached or gracefully degraded

### Online Mode
1. Hive data syncs to Firestore when connectivity detected
2. Gemini API handles multilingual assistant queries via FastAPI
3. Twilio dispatches weekly SMS summaries

## Privacy Design

- All health data encrypted with AES-256 before being written to Hive
- No data leaves the device unless user explicitly enables cloud sync
- Firestore security rules restrict read/write to authenticated user's own documents
- Backend never stores raw health data in logs

### Data portability & erasure

`services/data_privacy_service.py` owns both, and `api/privacy.py` exposes them under `/api/v1/privacy`. Every route operates strictly on `current_user["id"]` — none takes a user id from the path, so there is no authorization check to get wrong on an endpoint that hands out a full health export or destroys an account.

| Route | Purpose |
| :--- | :--- |
| `GET /privacy/summary` | Inventory: per category, how many records, which fields, the date range, the retention note. Field *names*, never values. |
| `GET /privacy/export?format=json\|csv` | The full bundle. JSON is canonical and versioned by `schema_version`; CSV is a flattened cycle-log table for spreadsheets. The password hash is excluded. |
| `POST /privacy/delete-account` | Two-step. Without a token: returns a single-use token plus an impact preview (202). With it: performs the cascade and returns per-collection counts (200). |
| `GET /privacy/deletion-status` | Confirms an account is gone, from the audit record. |

**One cascade, one list of collections.** `purge_user_data()` is the only implementation, and `UserService.delete_user()` (and therefore the existing `DELETE /auth/me`) delegates to it. Before this, `delete_user()` had its own partial cascade that covered `users`, `cycle_logs` and Firebase Auth but silently missed `conversations` — the assistant chat transcript, one document keyed by `user_id` — and the `rate_limits` documents keyed `sms:{user_id}`. A "successfully deleted" account left the user's health conversation in Firestore indefinitely. A new collection is now registered once in `USER_DATA_COLLECTIONS` and both deletion and the inventory pick it up.

**Rate-limit documents are found by id suffix**, not by a `user_id` field query — they don't have one, which is precisely why the query-based delete missed them.

**The audit record holds no personal data**: a SHA-256 of the user id, a timestamp, and the per-collection counts. Enough to answer "did you actually delete my data?" and to spot a purge that removed nothing; not enough to enumerate past users. It deliberately lives outside `USER_DATA_COLLECTIONS` so it survives the purge.

This is distinct from the PDF health report in [#228](https://github.com/ishita2740/Rhythma/issues/228): that is a human-readable summary for sharing with a clinician, this is machine-readable portability and erasure.

## ML Models

| Model | Purpose | Training Data |
|-------|---------|---------------|
| XGBoost | Cycle Variability Index (CVI) — 0–100 score | Synthetic + anonymized cycle datasets |
| Logistic Regression | Menstrual Health Score (MHS) — 0–100 score | Multi-factor wellness inputs |

Models are exported via `joblib` and bundled for on-device inference (planned: TFLite conversion for Flutter).

### AI Assistant Grounding

The assistant (`backend/api/assistant.py`) is grounded with a curated, sourced medical reference dataset (`backend/data/medical_references.json`) so its health answers come from trusted sources (WHO, NHS, and other approved organizations) instead of the model's memory. `backend/services/medical_knowledge_service.py` retrieves the entries relevant to each user message and embeds their facts and source URLs into the Gemini system prompt. Sourcing and citations policy live in [`medical_sources.md`](./medical_sources.md), and the dataset integrity is enforced by `backend/tests/test_medical_knowledge.py`.

## Planned: WhatsApp Integration

```
User (WhatsApp) ──► Twilio / Meta Cloud API ──► FastAPI webhook
                                                      │
                                               Gemini API (multilingual)
                                                      │
                                              Response back to user
```
## Frontend Clients

The repository contains two frontend implementations that share the same FastAPI backend:

* **`rhythma_flutter/` (Primary):** The primary cross-platform mobile application targeting Android, iOS, and Web. This is the main user experience, built to support offline-first operations via Hive local storage, secure on-device data encryption, and local CVI/MHS heuristics.
* **`web/` (React Web Client):** A browser-based React client built with Vite and TypeScript. It offers cycle tracking, the AI Assistant, Insights, Profile, Sharing, and a Clinic/Provider Dashboard. It communicates with the same FastAPI endpoints as the mobile client.

---

## Authentication Flow

Rhythma provides secure, token-based authentication supporting both email/password credentials and Firebase phone authentication.

```
┌─────────────────┐             ┌─────────────────┐
│  Credentials /  ├────────────►│  FastAPI /auth  │
│ Firebase Phone  │             │    Endpoints    │
└─────────────────┘             └────────┬────────┘
                                         │ Issues JWTs
                                ┌────────▼────────┐
                                │ Secure HttpOnly │
                                │  Auth Cookies   │
                                └─────────────────┘
```

### 1. Registration and Login Routes
* **Traditional Auth**:
  * `POST /api/v1/auth/register`: Accepts an email, password, and optional user profile fields. It enforces password complexity guidelines and sends an email verification token.
  * `POST /api/v1/auth/login`: Validates email and password, clears login rate limits on success, and issues JWT access/refresh tokens.
* **Firebase Phone Auth**:
  * `POST /api/v1/auth/firebase-login`: Accepts a Firebase `id_token` and optional FCM push token. The backend verifies the token via the Firebase Admin SDK, extracts the user's phone number, finds or creates the user in Firestore, and issues internal JWTs.

### 2. Token Issuance and Storage (HttpOnly Cookies)
The backend issues two JSON Web Tokens (JWTs) using the `HS256` signature algorithm:
* **Access Token**: Expires in 30 minutes.
* **Refresh Token**: Expires in 7 days.

**Client Platform Cookie Policy**:
* **Web Client (`web/`)**: Relies entirely on secure cookies for maximum security against Cross-Site Scripting (XSS).
  * Web requests carry the `X-Client-Platform: web` header.
  * The backend sets both `rhythma_access_token` and `rhythma_refresh_token` as `HttpOnly`, `Secure`, and `SameSite=Lax` cookies.
  * For web clients, the access token is omitted from the JSON response body to prevent JavaScript from accessing it.
* **Mobile Client (`rhythma_flutter/`)**: Reads the access and refresh tokens directly from the JSON response body and stores them in secure local storage. The backend still sets the cookies, but mobile requests typically authorize via headers.

### 3. Request Authorization
Protected API routes use the `get_current_user` dependency:
1. It first checks the HTTP `Authorization` header for a `Bearer <token>`.
2. If absent, it checks the incoming `rhythma_access_token` cookie.
3. If a valid token is found, it decodes the payload, extracts the user ID, fetches the corresponding user from Firestore, and injects the user context into the request handler.

### 4. Session Refresh (`/auth/refresh`)
To prevent session timeouts:
* The client sends a `POST /api/v1/auth/refresh` request containing the `refresh_token` in the request body.
* The backend verifies the token, revokes it (single-use / replay prevention), and returns a fresh access token and refresh token.
* *Note: Refresh tokens are stored in an in-memory dictionary on the backend, meaning active sessions are reset if the FastAPI server restarts.*

---

## Scoring Pipeline (CVI & MHS)

The Rhythma backend computes metrics about a user's cycle logs using both factual statistics and ML/heuristic scoring models.

```
┌───────────┐      Fetch Logs       ┌─────────────────┐      Extract Features      ┌─────────────────┐
│ Firestore │──────────────────────►│ scoring_service │───────────────────────────►│ build_features  │
└───────────┘     (Last 10 logs)    └─────────────────┘                            └────────┬────────┘
                                                                                            │
                                                                           ┌────────────────┴────────────────┐
                                                                           ▼                                 ▼
                                                                   ┌───────────────┐                 ┌───────────────┐
                                                                   │   predict_cvi │                 │  predict_mhs  │
                                                                   └───────┬───────┘                 └───────┬───────┘
                                                                           │ (XGBoost / Heuristic)           │ (Weighted Avg)
                                                                           ▼                                 ▼
                                                                      CVI Score                         MHS Score
                                                                       (0-100)                           (0-100)
```

### 1. Factual Cycle Statistics
Calculated directly in `compute_cycle_stats` from the user's `CycleLog` history in Firestore (up to the last 10 logs). These do not use model inference:
* **Average Cycle Length**: Average days between consecutive period start dates.
* **Shortest & Longest Cycle**: Boundary lengths observed in logs.
* **Average Bleeding Duration**: Mean number of bleeding days (start to end date inclusive).

### 2. Feature Engineering
Before feeding logs into the ML models, `build_model_features` transforms the raw log documents (ordered newest-first) into standard feature dictionaries containing:
* `cycle_length` (falls back to 28 days if history is short)
* `flow_duration` (defaults to 5 days)
* `flow_intensity` (mapped: none=0, light=1, medium=2, heavy=3; absent=2)
* `symptom_count` (length of symptoms array)
* `stress_avg` (average stress level 1-5, defaults to 2.5)
* `sleep_avg` (average sleep hours, defaults to 7.0)

### 3. Cycle Variability Index (CVI)
CVI measures cycle and symptoms instability (0-100, higher is more irregular):
* **Trigger**: Requires at least 3 logs.
* **Inference**: Loads the XGBoost model `cvi_model.joblib`.
* **Fallback**: If the model is not trained or found, it falls back to a standard deviation heuristic: `min(100.0, std_dev(cycle_lengths) * 8 + 30)`.
* **Tiers**: Low (<30), Medium (<65), High (>=65).

### 4. Menstrual Health Score (MHS)
MHS is a holistic score representing overall menstrual wellness (0-100, higher is better):
* **Trigger**: Requires at least 2 logs.
* **Calculation**: A weighted composite of five component scores:
  * **CVI Component** (30% weight): Calculated as `100 - CVI`.
  * **Sleep Score** (20% weight): Deviations from the optimal 7–9 hour window are penalized.
  * **Stress Score** (20% weight): Inverted stress level.
  * **Symptom Score** (15% weight): Penalizes high symptom counts.
  * **Lifestyle Score** (15% weight): Based on user profile's `exercise_frequency` and `diet_type` mapping. Defaults to 70.0 if profile is missing.

*For additional detail on MHS/CVI weighting, see issue #134.*

---

## Known Dev-Only Shortcuts

The following configuration choices and fallbacks are currently enabled to simplify local development, but are **not production-ready**.

| Dev Shortcut | File / Location | Why it's for Dev Only | Production Requirement | Tracking Issue |
| :--- | :--- | :--- | :--- | :--- |
| **Mock Firestore Fallback** | `backend/services/firestore_service.py`, `rhythma_flutter/lib/services/firestore_service.dart` | Allows local development without requiring live Firebase credentials by falling back to mock or stubbed data. | Require an active Firebase configuration with strict database security rules enforced. | N/A |
| **Cleartext Traffic Enabled** | `rhythma_flutter/android/app/src/main/AndroidManifest.xml` | Permits unencrypted HTTP communication for testing on local Android emulators/devices. | Enforce HTTPS exclusively (`android:usesCleartextTraffic="false"`) and configure a Network Security Config. | N/A |
| **Default HTTP `API_BASE_URL`** | `rhythma_flutter/lib/config/app_config.dart`, `rhythma_flutter/.env.example`, `README.md` | Defaults to non-secure `http://` local server URLs for quick setup. | Enforce secure `https://` base URLs passed via environment variables/production build configurations. | N/A |
| **In-Memory Session & Refresh Store** | `backend/core/auth.py` | Uses an in-memory dictionary to track active refresh tokens and temporary reset/verification codes, losing them on server restart. | Persist refresh tokens and codes in a database (e.g. Firestore) with secure expiration and cleanup jobs. | N/A |
