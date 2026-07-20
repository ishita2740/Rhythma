import 'package:flutter/foundation.dart';
import 'local_storage_service.dart';

// TODO: Uncomment when firebase_core + cloud_firestore are configured
// import 'package:cloud_firestore/cloud_firestore.dart';
// import 'package:firebase_auth/firebase_auth.dart';

/// Handles syncing local Hive data to Google Firestore.
/// Only runs when the user has enabled cloud sync in settings.
///
/// Architecture:
///   Hive (local, always) → [online + cloud_sync ON] → Firestore
///
/// Sensitive health data never leaves the device unless
/// cloudSyncEnabled == true.
class FirestoreService {
  // TODO: Replace with real Firestore instance after Firebase is configured
  // static final _db = FirebaseFirestore.instance;

  /// Sync all pending local cycle logs to Firestore.
  static Future<void> syncCycleLogs({required String userId}) async {
    if (!LocalStorageService.cloudSyncEnabled) {
      debugPrint('FirestoreService: cloud sync disabled, skipping.');
      return;
    }

    final logs = LocalStorageService.getCycleLogs();
    debugPrint('FirestoreService: syncing ${logs.length} logs for $userId');

    // TODO: Uncomment after Firebase setup
    // final batch = _db.batch();
    // for (final log in logs) {
    //   final ref = _db
    //       .collection('users')
    //       .doc(userId)
    //       .collection('cycle_logs')
    //       .doc(log['start_date'] as String);
    //   batch.set(ref, log, SetOptions(merge: true));
    // }
    // await batch.commit();

    debugPrint(
        'FirestoreService: sync complete (stub — Firebase not yet wired)');
  }

  /// Fetch cycle logs from Firestore and merge into local Hive storage.
  static Future<void> pullCycleLogs({required String userId}) async {
    if (!LocalStorageService.cloudSyncEnabled) return;

    // TODO: Uncomment after Firebase setup
    // final snapshot = await _db
    //     .collection('users')
    //     .doc(userId)
    //     .collection('cycle_logs')
    //     .orderBy('start_date', descending: true)
    //     .limit(24)
    //     .get();
    //
    // for (final doc in snapshot.docs) {
    //   await LocalStorageService.saveCycleLog(doc.data());
    // }

    debugPrint('FirestoreService: pull (stub — Firebase not yet wired)');
  }
}
