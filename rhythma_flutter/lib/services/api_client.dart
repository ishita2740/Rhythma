import 'package:dio/dio.dart';
import '../utils/secure_storage.dart';
import '../config/app_config.dart';

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

class ApiClient {
  static final Dio _dio = Dio(BaseOptions(
    baseUrl: AppConfig.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 10),
  ));
  static void Function()? _onUnauthorized;
  static bool _initialized = false;

  /// Shared in-progress refresh future so concurrent 401s do not spawn
  /// multiple refresh requests.
  static Future<String>? _refreshFuture;

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
          return handler.next(options);
        },
        onError: (error, handler) async {
          final statusCode = error.response?.statusCode;
          final requestPath = error.requestOptions.path;

          if (statusCode != 401) {
            // Not an auth error — pass through unchanged.
            return handler.next(error);
          }

          // ── 1. Skip public endpoints ────────────────────────────────
          if (_isPublicEndpoint(requestPath)) {
            return handler.next(error);
          }

          // ── 2. Prevent infinite retry loops ─────────────────────────
          // If this request was already retried after a refresh, give up
          // and force re-authentication.
          if (error.requestOptions.headers['X-Retry-After-Refresh'] == '1') {
            await SecureStorage.clearAuth();
            _onUnauthorized?.call();
            return handler.next(error);
          }

          // ── 3. Deduplicate concurrent refresh attempts ──────────────
          final refreshToken = await SecureStorage.getRefreshToken();
          if (refreshToken == null || refreshToken.isEmpty) {
            await SecureStorage.clearAuth();
            _onUnauthorized?.call();
            return handler.next(error);
          }

          try {
            final newToken = await _performRefresh(refreshToken);

            // ── 4. Retry the original request ─────────────────────────
            final retryOptions = error.requestOptions.copyWith(
              headers: {
                ...error.requestOptions.headers,
                'Authorization': 'Bearer $newToken',
                'X-Retry-After-Refresh': '1',
              },
            );
            final response = await _dio.fetch(retryOptions);
            return handler.resolve(response);
          } on DioException catch (refreshError) {
            // Refresh failed — clear everything and redirect to login.
            await SecureStorage.clearAuth();
            _onUnauthorized?.call();
            return handler.next(error);
          }
        },
      ),
    );
  }

  /// Calls `/auth/refresh` with the stored refresh token. If multiple
  /// requests fail with 401 at the same time, they all await the same
  /// single refresh future.
  static Future<String> _performRefresh(String refreshToken) async {
    // If a refresh is already in flight, reuse it.
    if (_refreshFuture != null) {
      return _refreshFuture!;
    }

    _refreshFuture = _doRefresh(refreshToken);
    try {
      final token = await _refreshFuture!;
      return token;
    } finally {
      _refreshFuture = null;
    }
  }

  static Future<String> _doRefresh(String refreshToken) async {
    final response = await _dio.post(
      '/auth/refresh',
      data: {'refresh_token': refreshToken},
    );

    final newAccessToken = response.data['access_token'] as String;
    final newRefreshToken = response.data['refresh_token'] as String;

    await SecureStorage.saveToken(newAccessToken);
    await SecureStorage.saveRefreshToken(newRefreshToken);

    return newAccessToken;
  }

  static Dio get dio => _dio;
}
