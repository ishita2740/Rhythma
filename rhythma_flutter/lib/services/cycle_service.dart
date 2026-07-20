import '../models/cycle_log.dart';
import 'api_client.dart';

/// Talks to the backend's `/cycle` endpoint. Local storage (Hive) is always
/// the source of truth for what the UI shows immediately; this is the
/// best-effort call that syncs a log to the backend so the dashboard's
/// real CVI/MHS scoring (which reads from Firestore, not the device) has
/// data to work with.
///
/// This intentionally does NOT maintain its own retry queue — offline
/// persistence and background sync for cycle data is Firestore's job (see
/// the offline-first Firestore sync work), not something to duplicate here.
/// A failed call simply throws so the caller can tell the user their entry
/// is saved locally but hasn't reached the server yet.
class CycleService {
  final _dio = ApiClient.dio;

  /// Submits a cycle log to the backend. Used both for a full Cycle-screen
  /// "Save" submission and a single-field Home quick-log tap — the backend
  /// upserts into that day's one document either way (see `POST /cycle/log`
  /// on the backend for why this doesn't create day-duplicates).
  Future<void> submitLog(CycleLog log) async {
    await _dio.post('/cycle/log', data: log.toJson());
  }
}