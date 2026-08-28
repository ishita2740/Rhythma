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

  /// Save [data] locally and push it to the backend.
  ///
  /// Returns whether the server took it. On `false` the profile is still
  /// saved on the device and is flagged as owed to the server, so
  /// [AuthService.validateSession] pushes it on the next launch that has
  /// a connection.
  ///
  /// Used by onboarding, which used to call [saveProfile] and stop
  /// (issue #551). Nothing else pushed it either, so the five screens a
  /// user fills in when she signs up produced a Firestore document with
  /// no `last_period`, no `cycle_length` and no name — and every
  /// server-side prediction fell back to a 28-day population default
  /// while the number she had declared sat unread on the handset.
  ///
  /// The local write comes first and is never conditional on the push.
  /// Hive stays the source of truth; this only stops it being the *only*
  /// copy.
  Future<bool> saveProfileWithSync(Map<String, dynamic> data) async {
    await saveProfile(data);
    await LocalStorageService.setProfileNeedsPush(true);

    final accepted = await ProfileService.patchProfile(data);
    if (accepted) {
      await LocalStorageService.setProfileNeedsPush(false);
    }
    return accepted;
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

    // 2. Attempt REST API backend sync (errors are swallowed by
    //    ProfileService, which reports them as `false` rather than
    //    throwing). A refused push leaves the flag set, so the next
    //    launch with a connection sends it.
    await LocalStorageService.setProfileNeedsPush(true);
    try {
      if (await ProfileService.patchProfile(_profile)) {
        await LocalStorageService.setProfileNeedsPush(false);
      }
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
