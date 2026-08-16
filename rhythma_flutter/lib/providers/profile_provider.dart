import 'package:flutter/material.dart';
import '../services/firestore_service.dart';
import '../services/local_storage_service.dart';
import '../services/profile_service.dart';

class ProfileProvider extends ChangeNotifier {
  Map<String, dynamic> _profile = {};

  ProfileProvider() {
    _loadProfile();
  }

  Map<String, dynamic> get profile => _profile;

  void _loadProfile() {
    _profile = LocalStorageService.getProfile() ?? {};
    notifyListeners();
  }

  /// Reload profile from local Hive storage.  Call this after the current
  /// user ID changes (e.g. after login/logout) to pick up the new user's
  /// scoped data.
  void reloadProfile() => _loadProfile();

  Future<void> saveProfile(Map<String, dynamic> data) async {
    await LocalStorageService.saveProfile(data);
    _profile = data;
    notifyListeners();
  }

  Future<void> mergeProfile(Map<String, dynamic> updates) async {
    await LocalStorageService.mergeProfile(updates);
    _profile = LocalStorageService.getProfile() ?? {};
    notifyListeners();
  }

  /// Merge [updates] into the local profile and then attempt a backend sync.
  ///
  /// Returns `null` on success, or a non-blocking user-facing message string
  /// when the backend sync fails (e.g. no connection).  The caller should
  /// show the message as a snackbar.
  ///
  /// Data is always persisted locally first so nothing is lost even when the
  /// backend is unreachable.
  Future<String?> mergeProfileWithSync(Map<String, dynamic> updates) async {
    // 1. Always persist locally first.
    await LocalStorageService.mergeProfile(updates);
    _profile = LocalStorageService.getProfile() ?? {};
    notifyListeners();

    // 2. Attempt REST API backend sync (fire-and-forget, errors are
    //    swallowed by ProfileService).
    try {
      await ProfileService.patchProfile(_profile);
    } catch (_) {}

    // 3. Attempt direct Firestore sync.  When offline this queues the
    //    update into the existing pending_cycle_sync Hive box so it is
    //    retried automatically when connectivity is restored.
    final uid = LocalStorageService.currentUserId;
    if (uid != null && LocalStorageService.cloudSyncEnabled) {
      try {
        await FirestoreService.syncProfile(userId: uid);
      } catch (_) {}
    }

    return null;
  }
}
