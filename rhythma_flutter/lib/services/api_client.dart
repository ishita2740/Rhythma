import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import '../utils/secure_storage.dart';
import '../config/app_config.dart';
import 'api_retry.dart';

/// Endpoints that should never trigger token refresh or retry logic.
/// These are either public or part of the auth flow itself.
const _publicEndpoints = {
  '/auth/login',
  '/auth/register',
  '/auth/firebase-login',
  '/auth/refresh',
  '/auth/logout',
  '/auth/password-requirements',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
  '/auth/resend-verification',
  '/assistant/languages',
  '/health',
};

bool _isPublicEndpoint(String path) {
  for (final public in _publicEndpoints) {
    if (path == public || path.endsWith(public)) return true;
  }
  return false;
}

/// Bookkeeping key for how many times *we* have replayed a request.
///
/// Kept in `RequestOptions.extra` rather than in a header: it is our own
/// counter and has no business being sent to the server, unlike
/// [kRetryAfterRefreshHeader], which the retried request genuinely carries
/// so the interceptor can recognise its own replay.
const String kRetryCountKey = 'rhythma.retryCount';

class ApiClient {
  static final Dio _dio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: kDefaultTimeout,
    receiveTimeout: kDefaultTimeout,
    // Previously unset, so a request whose *body* stalled mid-upload had
    // no deadline at all — the exact failure #408 was opened for on the
    // web, on the platform where it is most likely (#500).
    sendTimeout: kDefaultTimeout,
  ));

  static void Function()? _onUnauthorized;
  static bool _initialized = false;

  /// Shared in-progress refresh future so concurrent 401s do not spawn
  /// multiple refresh requests.
  static Future<String>? _refreshFuture;

  /// When to retry, and how long to wait first.
  ///
  /// Mutable so a test can substitute a policy with deterministic jitter
  /// and a stubbed connectivity probe, rather than waiting out real
  /// backoff or reaching for a platform channel.
  static RetryPolicy retryPolicy = const RetryPolicy(
    isOffline: _deviceIsOffline,
  );

  /// Whether the device has no network at all.
  ///
  /// Only trusted in the negative direction, the same way the web client
  /// treats `navigator.onLine`: "no interface" reliably means nothing will
  /// get through, while "has an interface" says nothing about whether the
  /// backend is reachable. A failure of the probe itself is handled by
  /// [RetryPolicy.shouldSuppressForOffline] as "we do not know", which
  /// lets the retry proceed.
  static Future<bool> _deviceIsOffline() async {
    final results = await Connectivity().checkConnectivity();
    return results.isEmpty ||
        results.every((result) => result == ConnectivityResult.none);
  }

  static void init({void Function()? onUnauthorized}) {
    _onUnauthorized = onUnauthorized;
    if (_initialized) return;
    _initialized = true;
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await SecureStorage.getToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }

          // The assistant waits on a model call and legitimately runs
          // longer than the default deadline. Raising the instance-wide
          // timeout to suit it would give every other endpoint a
          // 45-second window in which to hang, so the exception is
          // per-path (#500) — the same split `web/src/api/client.ts`
          // makes.
          final deadline = retryPolicy.timeoutFor(options.path);
          options.connectTimeout = deadline;
          options.receiveTimeout = deadline;
          options.sendTimeout = deadline;

          return handler.next(options);
        },
        onError: (error, handler) async {
          final statusCode = error.response?.statusCode;
          final requestPath = error.requestOptions.path;

          if (statusCode != 401) {
            // ── Transient failures (#500) ─────────────────────────────
            //
            // Handled before the 401 branch and kept entirely separate
            // from it. The two paths use different counters — `extra`
            // here, the `X-Retry-After-Refresh` header below — so a
            // request replayed after a token refresh does not also
            // consume its transient budget, and neither can multiply
            // against the other.
            final attempt =
                (error.requestOptions.extra[kRetryCountKey] as int?) ?? 0;

            if (retryPolicy.shouldRetry(error, attempt)) {
              // No point spending the budget on requests that cannot
              // succeed. Checked here rather than inside `shouldRetry` so
              // that decision stays a pure function of the error.
              if (await retryPolicy.shouldSuppressForOffline()) {
                return handler.next(error);
              }

              final retryAfter =
                  parseRetryAfter(retryAfterHeaderOf(error.response));
              await Future<void>.delayed(
                retryPolicy.backoffDelay(attempt, retryAfter: retryAfter),
              );

              final retryOptions = error.requestOptions
                ..extra[kRetryCountKey] = attempt + 1;

              try {
                final response = await _dio.fetch(retryOptions);
                return handler.resolve(response);
              } on DioException catch (retryError) {
                return handler.next(retryError);
              }
            }

            // Not a 401 and not worth retrying — pass through unchanged.
            return handler.next(error);
          }

          // ── 1. Skip public endpoints ────────────────────────────────
          if (_isPublicEndpoint(requestPath)) {
            return handler.next(error);
          }

          // ── 2. Prevent infinite retry loops ─────────────────────────
          // If this request was already retried after a refresh, give up
          // and force re-authentication.
          if (error.requestOptions.headers[kRetryAfterRefreshHeader] == '1') {
            await _forceReauthentication();
            return handler.next(error);
          }

          // ── 3. Deduplicate concurrent refresh attempts ──────────────
          final refreshToken = await SecureStorage.getRefreshToken();
          if (refreshToken == null || refreshToken.isEmpty) {
            await _forceReauthentication();
            return handler.next(error);
          }

          final String newToken;
          try {
            newToken = await _performRefresh(refreshToken);
          } catch (_) {
            // Deliberately `catch (_)` and not `on DioException`.
            //
            // `_doRefresh` can fail without a `DioException`: a 200 whose
            // body is a proxy's HTML error page, or a field renamed on the
            // server, made the old cast throw a `TypeError`. That escaped
            // this interceptor entirely — credentials were left in place,
            // `_onUnauthorized` was never called, and the caller's future
            // settled in a way it did not expect while the user sat there
            // signed in with a dead token (#500).
            await _forceReauthentication();
            return handler.next(error);
          }

          // ── 4. Retry the original request ─────────────────────────
          final retryOptions = error.requestOptions.copyWith(
            headers: {
              ...error.requestOptions.headers,
              'Authorization': 'Bearer $newToken',
              kRetryAfterRefreshHeader: '1',
            },
          );

          try {
            final response = await _dio.fetch(retryOptions);
            return handler.resolve(response);
          } on DioException catch (retryError) {
            return handler.next(retryError);
          }
        },
      ),
    );
  }

  /// Drop the stored credentials and tell the app to send the user to login.
  ///
  /// One place, because every branch above that gives up on a session has
  /// to do both, and doing only the first leaves the app looking signed in
  /// while every request 401s.
  static Future<void> _forceReauthentication() async {
    await SecureStorage.clearAuth();
    _onUnauthorized?.call();
  }

  /// Calls `/auth/refresh` with the stored refresh token. If multiple
  /// requests fail with 401 at the same time, they all await the same
  /// single refresh future.
  static Future<String> _performRefresh(String refreshToken) async {
    // If a refresh is already in flight, reuse it.
    final inFlight = _refreshFuture;
    if (inFlight != null) {
      return inFlight;
    }

    final future = _doRefresh(refreshToken);
    _refreshFuture = future;
    try {
      return await future;
    } finally {
      _refreshFuture = null;
    }
  }

  static Future<String> _doRefresh(String refreshToken) async {
    final response = await _dio.post(
      '/auth/refresh',
      data: {'refresh_token': refreshToken},
    );

    // Read defensively rather than casting. A 200 carrying something other
    // than the expected envelope is a real possibility — a captive portal,
    // a proxy error page, a renamed field — and a `TypeError` raised here
    // is far harder to recover from than a refresh that reports failure.
    final data = response.data;
    final newAccessToken = data is Map ? data['access_token'] : null;
    final newRefreshToken = data is Map ? data['refresh_token'] : null;

    if (newAccessToken is! String || newAccessToken.isEmpty) {
      throw DioException(
        requestOptions: response.requestOptions,
        response: response,
        type: DioExceptionType.badResponse,
        error: 'Refresh response carried no access token.',
      );
    }

    await SecureStorage.saveToken(newAccessToken);
    if (newRefreshToken is String && newRefreshToken.isNotEmpty) {
      // A backend that rotates refresh tokens sends a new one; one that
      // does not, does not. Storing `null` in the second case would sign
      // the user out at the next refresh.
      await SecureStorage.saveRefreshToken(newRefreshToken);
    }

    return newAccessToken;
  }

  static Dio get dio => _dio;
}
