import 'package:flutter/material.dart';
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

    // 2. Attempt backend sync with the full (merged) profile.
    try {
      await ProfileService.patchProfile(_profile);
      return null; // success
    } catch (_) {
      return 'Changes saved locally. They will sync when connection returns.';
    }
  }
}
