import 'package:dio/dio.dart';
import 'api_client.dart';

/// ProfileService — offline-safe bridge between the Flutter app and the
/// backend `/api/v1/auth/profile` endpoints introduced in the
/// auth-onboarding-integration feature.
///
/// Design contract:
/// • Local Hive storage (via LocalStorageService) is always the source
///   of truth.  The backend is a sync target, not the primary store.
/// • All methods swallow network / server errors so callers never need
///   to guard against connectivity issues.  Callers save locally first,
///   then call these helpers; if the backend is down, data is preserved.
class ProfileService {
  static final Dio _dio = ApiClient.dio;

  /// PATCH `/api/v1/auth/profile` — merge [data] onto the backend user
  /// document.  Only non-null values are sent.
  ///
  /// Silently swallows all errors (connection, timeout, 5xx, etc.).
  /// The caller should always persist locally before calling this.
  static Future<void> patchProfile(Map<String, dynamic> data) async {
    try {
      // Strip out fields the backend profile endpoint doesn't accept
      // (e.g. internal Hive keys, phone number formatting artefacts).
      final payload = _buildPayload(data);
      if (payload.isEmpty) return;
      await _dio.patch('/auth/profile', data: payload);
    } on DioException catch (_) {
      // Network unavailable, timeout, or server error — all are expected
      // in offline-first usage.  Local Hive data is already saved.
    } catch (_) {
      // Any unexpected error — never bubble up to the user.
    }
  }

  /// GET `/api/v1/auth/profile` — fetch the full profile from the backend.
  ///
  /// Returns a [Map] of profile fields on success, or `null` on any
  /// failure (caller should fall back to the local Hive cache).
  static Future<Map<String, dynamic>?> fetchProfile() async {
    try {
      final response = await _dio.get('/auth/profile');
      if (response.statusCode == 200 && response.data is Map) {
        return Map<String, dynamic>.from(response.data as Map);
      }
      return null;
    } on DioException catch (_) {
      return null;
    } catch (_) {
      return null;
    }
  }

  // ── Internal helpers ───────────────────────────────────────────────────────

  /// Map Hive profile keys to the fields accepted by [UserProfileUpdate].
  ///
  /// Only fields recognised by the backend model are forwarded.  All
  /// others (e.g. internal flags like `phone`, `city`, `state`) are
  /// included if they exist in the local profile.
  static Map<String, dynamic> _buildPayload(Map<String, dynamic> data) {
    const _allowed = {
      'full_name',
      'age',
      'height_cm',
      'weight_kg',
      'avatar',
      'language',
      'last_period',
      'cycle_length',
      'period_duration',
      'cycle_regular',
      'notifications_enabled',
      'phone',
      'city',
      'state',
    };

    final payload = <String, dynamic>{};

    for (final key in _allowed) {
      if (data.containsKey(key) && data[key] != null) {
        payload[key] = data[key];
      }
    }

    // 'name' in Hive corresponds to 'full_name' on the backend
    if (!payload.containsKey('full_name') &&
        data.containsKey('name') &&
        data['name'] != null) {
      payload['full_name'] = data['name'];
    }

    return payload;
  }
}
