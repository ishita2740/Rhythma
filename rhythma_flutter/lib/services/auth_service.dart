import 'package:dio/dio.dart';
import '../models/user.dart';
import '../utils/secure_storage.dart';
import 'api_client.dart';
import 'firestore_service.dart';
import 'local_storage_service.dart';
import 'profile_service.dart';

class AuthService {
  final Dio _dio = ApiClient.dio;

  Future<String> firebaseLogin(String idToken) async {
    try {
      final response = await _dio.post(
        '/auth/firebase-login',
        data: {
          'id_token': idToken,
        },
      );
      final token = response.data['access_token'] as String;
      await SecureStorage.saveToken(token);

      // Save refresh token if present (now returned by backend)
      final refreshToken = response.data['refresh_token'] as String?;
      if (refreshToken != null && refreshToken.isNotEmpty) {
        await SecureStorage.saveRefreshToken(refreshToken);
      }

      // Scope local (profile/chat history/cycle log) storage to this
      // account so multiple accounts on the same device don't share data.
      try {
        final me = await _dio.get('/auth/me');
        final uid = (me.data as Map<String, dynamic>)['id']?.toString();
        if (uid != null) {
          await LocalStorageService.setCurrentUserId(uid);
          await _syncProfile(uid);
          // Sync local data with Firestore and pull remote data
          FirestoreService.pullCycleLogs(userId: uid);
          FirestoreService.pullProfile(userId: uid);
          FirestoreService.syncCycleLogs(userId: uid);
          FirestoreService.syncProfile(userId: uid);
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

  /// The server fields that map onto a local profile key.
  ///
  /// `full_name` is stored locally as `name`; everything else keeps its
  /// name. Listed rather than copied wholesale so a field the backend
  /// adds does not silently land in local storage under a key no screen
  /// reads.
  static const Map<String, String> _serverToLocalProfileKeys = {
    'full_name': 'name',
    'avatar': 'avatar',
    'language': 'language',
    'age': 'age',
    'height_cm': 'height_cm',
    'weight_kg': 'weight_kg',
    'last_period': 'last_period',
    'last_period_is_approximate': 'last_period_is_approximate',
    'cycle_length': 'cycle_length',
    'period_duration': 'period_duration',
    'cycle_regular': 'cycle_regular',
    'phone': 'phone',
    'city': 'city',
    'state': 'state',
    'notifications_enabled': 'notifications_enabled',
  };

  /// Reconcile the account's profile between this device and the server.
  ///
  /// Push first, then pull. The device is the source of truth for
  /// anything it has that the server has not accepted yet — which, until
  /// issue #551, was *everything a user entered during onboarding*,
  /// because that screen wrote Hive and never called the API. Pulling
  /// before pushing would let a near-empty server document decide what
  /// the handset knows.
  ///
  /// The pull **merges**. It used to rebuild the local profile from a
  /// whitelist and `saveProfile` it, which replaces — so any local-only
  /// field was dropped on every cold start, and a server document with no
  /// `full_name` renamed the user to the literal string `User` and reset
  /// her avatar to `avatar_1`. Every launch.
  ///
  /// The whole thing used to be gated on `profile['cycle_length'] != null`,
  /// so an account whose server copy had no cycle length — which is every
  /// account, given the missing push — synced nothing at all. Only
  /// `setOnboardingCompleted` still depends on it, which is the one thing
  /// it genuinely means: this account finished onboarding somewhere.
  Future<void> _syncProfile(String uid) async {
    try {
      if (LocalStorageService.profileNeedsPush) {
        final local = LocalStorageService.getProfile();
        if (local != null && local.isNotEmpty) {
          if (await ProfileService.patchProfile(local)) {
            await LocalStorageService.setProfileNeedsPush(false);
          }
        } else {
          // Nothing to send: the flag outlived the data it referred to.
          await LocalStorageService.setProfileNeedsPush(false);
        }
      }

      final profileResponse = await _dio.get('/auth/profile');
      if (profileResponse.statusCode == 200 && profileResponse.data is Map) {
        final profile = Map<String, dynamic>.from(profileResponse.data as Map);

        if (profile['cycle_length'] != null) {
          await LocalStorageService.setOnboardingCompleted(true);
        }

        final fromServer = <String, dynamic>{};
        _serverToLocalProfileKeys.forEach((serverKey, localKey) {
          final value = profile[serverKey];
          // A null is "the server does not hold this", not "clear it".
          // Treating the two the same is what let an empty server
          // document overwrite a name and an avatar the user had chosen.
          if (value != null) fromServer[localKey] = value;
        });

        if (fromServer.isNotEmpty) {
          await LocalStorageService.mergeProfile(fromServer);
        }
      }
    } catch (_) {
      // Non-fatal
    }
  }

  Future<void> logout() async {
    await SecureStorage.clearAuth();
    // Clears which account is "active" locally — does not delete that
    // account's cached data, so it's still there if they log back in.
    await LocalStorageService.setCurrentUserId(null);
  }

  Future<void> deleteAccount() async {
    try {
      await _dio.delete('/auth/me');
    } catch (_) {
      // Best effort deletion on the server, but we must delete locally regardless
    }
    await SecureStorage.clearAuth();
    await LocalStorageService.deleteCurrentUserData();
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
        // Sync local data with Firestore and pull remote data
        FirestoreService.pullCycleLogs(userId: uid);
        FirestoreService.pullProfile(userId: uid);
        FirestoreService.syncCycleLogs(userId: uid);
        FirestoreService.syncProfile(userId: uid);
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
