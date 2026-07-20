import 'package:dio/dio.dart';
import 'api_client.dart';

/// Thin wrapper around the backend's existing `/sms` endpoints
/// (`/sms/settings`, `/sms/send-summary`). No backend changes were needed
/// for issue #26 — this only calls what already exists.
class SmsService {
  final Dio _dio = ApiClient.dio;

  /// Fetches the signed-in user's saved phone number and whether weekly
  /// SMS summaries are enabled.
  Future<Map<String, dynamic>> getSettings() async {
    final response = await _dio.get('/sms/settings');
    return Map<String, dynamic>.from(response.data as Map);
  }

  /// Saves the phone number and enabled state for weekly SMS summaries.
  Future<Map<String, dynamic>> saveSettings({
    required String phoneNumber,
    required bool enabled,
  }) async {
    final response = await _dio.post('/sms/settings', data: {
      'phoneNumber': phoneNumber,
      'enabled': enabled,
    });
    return Map<String, dynamic>.from(response.data as Map);
  }

  /// Sends an on-demand SMS summary to [phoneNumber] right now.
  Future<void> sendSummary({
    required String phoneNumber,
    required String message,
  }) async {
    await _dio.post('/sms/send-summary', data: {
      'phone_number': phoneNumber,
      'message': message,
    });
  }
}