import 'package:dio/dio.dart';
import '../models/user.dart';
import '../utils/secure_storage.dart';
import 'api_client.dart';
import 'local_storage_service.dart';

class AuthService {
  final Dio _dio = ApiClient.dio;

  Future<User> register(
      String username, String email, String password, String? fullName) async {
    try {
      final response = await _dio.post(
        '/auth/register',
        data: {
          'username': username,
          'email': email,
          'password': password,
          'full_name': fullName,
        },
      );
      return User.fromJson(response.data);
    } on DioException catch (e) {
      throw AuthException(
          _readErrorMessage(e, 'Registration failed. Please try again.'));
    }
  }

  Future<String> login(String username, String password) async {
    try {
      final response = await _dio.post(
        '/auth/token',
        data: {
          'username': username,
          'password': password,
        },
        options: Options(
          contentType: Headers.formUrlEncodedContentType,
        ),
      );
      final token = response.data['access_token'] as String;
      await SecureStorage.saveToken(token);

      // Scope local (profile/chat history/cycle log) storage to this
      // account so multiple accounts on the same device don't share data.
      try {
        final me = await _dio.get('/auth/me');
        final uid = (me.data as Map<String, dynamic>)['id']?.toString();
        if (uid != null) {
          await LocalStorageService.setCurrentUserId(uid);
          await _syncProfile(uid);
        }
      } catch (_) {
        // Non-fatal — login itself already succeeded. Scoping will simply
        // kick in next time validateSession() runs (e.g. next app launch).
      }

      return token;
    } on DioException catch (e) {
      throw AuthException(
          _readErrorMessage(e, 'Login failed. Please check your details.'));
    }
  }

  Future<void> _syncProfile(String uid) async {
    try {
      final profileResponse = await _dio.get('/auth/profile');
      if (profileResponse.statusCode == 200 && profileResponse.data is Map) {
        final profile = Map<String, dynamic>.from(profileResponse.data as Map);
        if (profile['cycle_length'] != null) {
          await LocalStorageService.setOnboardingCompleted(true);
          final localProfile = <String, dynamic>{
            'name': profile['full_name'] ?? 'User',
            'avatar': profile['avatar'] ?? 'assets/avatars/avatar_1.png',
            'language': profile['language'] ?? 'en',
          };
          if (profile['age'] != null) localProfile['age'] = profile['age'];
          if (profile['height_cm'] != null)
            localProfile['height_cm'] = profile['height_cm'];
          if (profile['weight_kg'] != null)
            localProfile['weight_kg'] = profile['weight_kg'];
          if (profile['last_period'] != null)
            localProfile['last_period'] = profile['last_period'];
          if (profile['cycle_length'] != null)
            localProfile['cycle_length'] = profile['cycle_length'];
          if (profile['period_duration'] != null)
            localProfile['period_duration'] = profile['period_duration'];
          if (profile['cycle_regular'] != null)
            localProfile['cycle_regular'] = profile['cycle_regular'];
          if (profile['phone'] != null)
            localProfile['phone'] = profile['phone'];
          if (profile['city'] != null) localProfile['city'] = profile['city'];
          if (profile['state'] != null)
            localProfile['state'] = profile['state'];
          if (profile['notifications_enabled'] != null) {
            localProfile['notifications_enabled'] =
                profile['notifications_enabled'];
          }
          await LocalStorageService.saveProfile(localProfile);
        }
      }
    } catch (_) {
      // Non-fatal
    }
  }

  Future<void> logout() async {
    await SecureStorage.deleteToken();
    // Clears which account is "active" locally — does not delete that
    // account's cached data, so it's still there if they log back in.
    await LocalStorageService.setCurrentUserId(null);
  }

  Future<bool> isLoggedIn() async {
    return await SecureStorage.hasToken();
  }

  /// Confirms a locally stored token is still genuinely valid (not just
  /// present) by calling the lightweight `/auth/me` endpoint, and scopes
  /// local storage to the resulting user id. Used at app launch instead of
  /// just checking for token existence.
  ///
  /// Returns the user id if the session is valid, or null if there's no
  /// token or the server has confirmed it's no longer valid (expired,
  /// tampered, or the account no longer exists).
  ///
  /// A network failure (offline, timeout) is treated as "can't confirm
  /// either way" rather than "invalid" — we fall back to whatever user id
  /// was cached from the last successful validation, so the app remains
  /// usable offline instead of forcing a logout just because the network
  /// request itself failed.
  Future<String?> validateSession() async {
    if (!await SecureStorage.hasToken()) return null;

    try {
      final response = await _dio.get('/auth/me');
      final uid = (response.data as Map<String, dynamic>)['id']?.toString();
      if (uid != null) {
        await LocalStorageService.setCurrentUserId(uid);
        await _syncProfile(uid);
      }
      return uid;
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        // Definitely invalid. ApiClient's onError interceptor already
        // clears the stored token when this happens.
        return null;
      }
      // Couldn't reach the server — don't force a logout for that alone.
      return LocalStorageService.currentUserId;
    }
  }

  String _readErrorMessage(DioException error, String fallback) {
    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.sendTimeout ||
        error.type == DioExceptionType.receiveTimeout) {
      return 'Request timed out. Please try again.';
    }

    if (error.type == DioExceptionType.connectionError) {
      return 'Network unavailable. Please check your internet connection.';
    }

    final response = error.response;
    if (response != null) {
      final data = response.data;
      if (data is Map<String, dynamic>) {
        final detail = data['detail'];
        if (detail is String && detail.trim().isNotEmpty) return detail;
        if (detail is List && detail.isNotEmpty) return detail.first.toString();
      }

      if (response.statusCode == 401) {
        return 'Invalid credentials. Please verify your username and password.';
      }
      if (response.statusCode == 404) {
        return 'Profile lookup failed. Resource not found.';
      }
      if (response.statusCode != null && response.statusCode! >= 500) {
        return 'Server error (${response.statusCode}). Please try again later.';
      }
    }

    return fallback;
  }
}

class AuthException implements Exception {
  final String message;

  const AuthException(this.message);

  @override
  String toString() => message;
}
