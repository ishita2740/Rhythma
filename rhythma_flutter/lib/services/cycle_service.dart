import 'package:dio/dio.dart';
import '../models/cycle_log.dart';
import 'api_client.dart';
import 'offline_sync_service.dart';

/// Talks to the backend's `/cycle` endpoint. Local storage (Hive) is always
/// the source of truth for what the UI shows immediately; this is the
/// best-effort call that syncs a log to the backend so the dashboard's
/// real CVI/MHS scoring (which reads from Firestore, not the device) has
/// data to work with.
///
/// On network failure, mutations are queued in [OfflineSyncService] for
/// automatic retry when connectivity is restored.
class CycleService {
  final _dio = ApiClient.dio;

  /// Submits a cycle log to the backend. Used both for a full Cycle-screen
  /// "Save" submission and a single-field Home quick-log tap — the backend
  /// upserts into that day's one document either way (see `POST /cycle/log`
  /// on the backend for why this doesn't create day-duplicates).
  ///
  /// Returns `true` if the log was synced to the server, `false` if it was
  /// queued for offline retry.
  Future<bool> submitLog(CycleLog log) async {
    try {
      await _dio.post('/cycle/log', data: log.toJson());
      return true;
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        await OfflineSyncService.enqueueUpsert(
          dateKey: log.toJson()['start_date'] as String,
          payload: log.toJson(),
        );
        return false;
      }
      rethrow;
    }
  }

  /// Deletes a cycle log entry for [logId] (the date string YYYY-MM-DD)
  /// on the backend. Returns `true` if the delete was synced to the server,
  /// `false` if it was queued for offline retry.
  Future<bool> deleteLog(String logId) async {
    try {
      await _dio.delete('/cycle/$logId');
      return true;
    } on DioException catch (e) {
      if (_isNetworkError(e)) {
        await OfflineSyncService.enqueueDelete(dateKey: logId);
        return false;
      }
      rethrow;
    }
  }

  /// Checks if a DioException is a network/connectivity error that should
  /// trigger offline queuing rather than being surfaced to the user.
  static bool _isNetworkError(DioException e) {
    return e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.unknown;
  }

  /// Fetches a paginated list of cycle history for the user.
  Future<Map<String, dynamic>> getCycleHistory(String userId, {int offset = 0, int limit = 15}) async {
    final response = await _dio.get(
      '/cycle/$userId/history',
      queryParameters: {
        'offset': offset,
        'limit': limit,
      },
    );
    return response.data;
  }
}