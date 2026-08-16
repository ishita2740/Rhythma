# Automatic Access-Token Refresh

This document describes the automatic token-refresh flow implemented for both the Flutter (mobile) and Web clients. The backend already provides an `/auth/refresh` endpoint; this document covers how both clients use it reliably when access tokens expire.

---

## Overview

```
Authenticated request
        ↓
Access token expired
        ↓
API returns 401
        ↓
Client calls /auth/refresh
        ↓
Refresh succeeds?
    ↙           ↘
  Yes            No
   ↓              ↓
Store new       Clear session
access token    and authenticate again
   ↓
Retry original request once
```

---

## Backend Changes (`backend/core/auth_router.py`)

### `/auth/firebase-login`
- **Before**: Returned only `access_token` for Flutter; no refresh token was created.
- **After**: Creates a refresh token, sets the `rhythma_refresh_token` HttpOnly cookie, and returns `refresh_token` in the JSON body for Flutter clients.

### `/auth/refresh` — Dual-Mode
- **Body mode**: Flutter/mobile clients send `{"refresh_token": "..."}` in the request body.
- **Cookie mode**: Web clients rely on the `rhythma_refresh_token` HttpOnly cookie (sent automatically via `withCredentials`). The backend reads the cookie when no body token is present.
- **On success**: Rotates both the access token (new cookie) and refresh token (new cookie), and returns both tokens in the JSON body.

### `/auth/logout`
- **Before**: Cleared only the access token cookie.
- **After**: Clears both `rhythma_access_token` and `rhythma_refresh_token` cookies.

---

## Flutter Client (`rhythma_flutter/`)

### Files Modified
- `lib/utils/secure_storage.dart` — Added `saveRefreshToken`, `getRefreshToken`, `deleteRefreshToken`, `hasRefreshToken`, `clearAuth`.
- `lib/services/auth_service.dart` — `firebaseLogin()` now saves the refresh token; `logout()` calls `SecureStorage.clearAuth()`.
- `lib/services/api_client.dart` — Complete rewrite of the interceptor with auto-refresh logic.

### Interceptor Behavior
1. **Request**: Attaches `Authorization: Bearer <access_token>` if present.
2. **Response 401**:
   - Skip if endpoint is public (`/auth/login`, `/auth/register`, etc.).
   - Skip if request already has `X-Retry-After-Refresh: 1` (infinite loop prevention).
   - Check if a refresh is already in progress → await the shared future.
   - Call `/auth/refresh` with the stored refresh token.
   - On success: save new access + refresh tokens, retry original request once.
   - On failure: clear all auth state, call `onUnauthorized` (redirects to `/login`).

### Concurrent Request Deduplication
A `static Future<String>? _refreshFuture` ensures that if 5 requests fail with 401 simultaneously, only **one** refresh request is sent. All 5 requests await the same future and retry with the new token.

### Tests
- `test/services/api_client_test.dart` — 9 tests covering:
  - Valid token request
  - Expired token → refresh → retry
  - Invalid refresh token → logout
  - Concurrent requests share one refresh
  - No infinite retry loops
  - Preserved method/headers/body on retry
  - Public endpoints skip refresh
  - Second 401 after refresh forces logout

---

## Web Client (`web/`)

### Files Modified
- `src/api/client.ts` — Added auto-refresh interceptor with cookie-based flow.
- `src/api/client.test.ts` — Extended tests for refresh logic.

### Interceptor Behavior
1. **Request**: No `Authorization` header (relies on HttpOnly cookie).
2. **Response 401**:
   - Skip if endpoint is public.
   - Skip if request already has `X-Retry-After-Refresh: 1`.
   - Check if a refresh is already in progress → await the shared promise.
   - Call `/auth/refresh` with `withCredentials: true` (cookie auto-sent).
   - On success: retry original request (new cookies auto-sent).
   - On failure: call `onUnauthorized` (redirects to `/login`).

### Concurrent Request Deduplication
A module-level `let refreshPromise: Promise<boolean> | null` ensures only one refresh request is in flight at a time.

### Tests
- `src/api/client.test.ts` — Extended with tests for:
  - Refresh + retry on 401
  - Refresh failure → logout
  - Infinite loop prevention (`X-Retry-After-Refresh`)
  - Concurrent 401 deduplication

---

## Security Considerations

1. **Token Rotation**: Every successful refresh revokes the old refresh token and issues a new one. This prevents replay attacks if a refresh token is leaked.
2. **HttpOnly Cookies**: Web clients never touch refresh tokens in JavaScript. The cookie is `HttpOnly`, `Secure` (in production), and `SameSite=lax`.
3. **Rate Limiting**: `/auth/refresh` is rate-limited per IP to prevent brute-force guessing of refresh tokens.
4. **Infinite Loop Prevention**: The `X-Retry-After-Refresh` header ensures a request is never retried more than once after a refresh.

---

## Testing

### Backend
```bash
cd backend
pytest tests/test_auth.py -v
```

### Flutter
```bash
cd rhythma_flutter
flutter test test/services/api_client_test.dart
```

### Web
```bash
cd web
npm test
```
