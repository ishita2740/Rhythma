import 'dart:async';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'local_storage_service.dart';
import '../providers/sync_status_provider.dart';

/// Handles offline-first Firestore synchronization.
///
/// Architecture:
/// - Hive (local) is always the source of truth for reads
/// - Firestore syncs when online + cloudSyncEnabled == true
/// - Pending writes queued in Hive under 'pending_cycle_sync' box
/// - Automatic retry on connectivity restore
/// - Last-write-wins conflict resolution (server timestamp wins)
///
/// Everything crossing back from Firestore into Hive goes through
/// [toStorable] (issue #550). Hive encodes `int`, `double`, `bool`,
/// `String`, `List`, `Map`, `DateTime` and `Uint8List`, plus anything with
/// a registered `TypeAdapter` — and this app registers none. A Firestore
/// document carries a `Timestamp` under `synced_at`, so every write-back
/// here used to throw
///
///     HiveError: Cannot write, unknown type: Timestamp.
///
/// on the first document it was handed. That single throw is the reason
/// cloud sync never completed: [syncCycleLogs] committed its batch, blew
/// up reading the result back, caught its own exception and re-queued the
/// entire history — which the next flush pushed again, and the next sync
/// re-queued again. [pullCycleLogs] aborted on its first document, so no
/// remote log was ever merged.
///
/// It also silently disabled the conflict resolution the class is built
/// on. The local half of every `synced_at` comparison was read back out of
/// Hive, where a `Timestamp` had never been storable, so `localTime` was
/// always null and the server unconditionally won. Last-write-wins had no
/// local write to compare against.
class FirestoreService {
  static FirebaseFirestore? _db;
  static StreamSubscription<List<ConnectivityResult>>?
      _connectivitySubscription;
  static final Connectivity _connectivity = Connectivity();
  static bool _initialized = false;
  static bool _isSyncing = false;

  /// Safe wrappers: only call SyncStatusProvider if the provider exists.
  static void _updateStatus(SyncStatus status, String type, {String? error}) {
    if (SyncStatusProvider.hasInstance) {
      SyncStatusProvider.instance.updateStatus(status, type, error: error);
    }
  }

  static void _setOnline() {
    if (SyncStatusProvider.hasInstance) {
      SyncStatusProvider.instance.setOnline();
    }
  }

  static void _setOffline() {
    if (SyncStatusProvider.hasInstance) {
      SyncStatusProvider.instance.setOffline();
    }
  }

  // ────────────────────────────────────────────────────────────────────────────
  // FIRESTORE <-> HIVE CONVERSION
  // ────────────────────────────────────────────────────────────────────────────

  /// A Firestore document rewritten as something Hive can encode.
  ///
  /// See the class docstring for what happened without this. The mapping
  /// is deliberately lossy in one direction only: a `Timestamp` becomes an
  /// ISO-8601 string, which [syncedAt] reads back into a `DateTime` for
  /// the comparison that actually uses it. ISO strings are also what the
  /// pending queue already stores under `queued_at` and what `start_date`
  /// is, so the local documents stay one shape rather than two.
  @visibleForTesting
  static Map<String, dynamic> toStorable(Map<String, dynamic> data) {
    return data.map((key, value) => MapEntry(key, _storableValue(value)));
  }

  static dynamic _storableValue(dynamic value) {
    if (value is Timestamp) return value.toDate().toUtc().toIso8601String();
    if (value is DateTime) return value.toUtc().toIso8601String();
    if (value is DocumentReference) return value.path;
    if (value is GeoPoint) {
      return {'latitude': value.latitude, 'longitude': value.longitude};
    }
    if (value is Map) {
      return value.map<String, dynamic>(
        (key, nested) => MapEntry(key.toString(), _storableValue(nested)),
      );
    }
    if (value is List) return value.map(_storableValue).toList();
    return value;
  }

  /// The `synced_at` of a document, whichever side it came from.
  ///
  /// A document straight off Firestore carries a `Timestamp`; the same
  /// document read back out of Hive carries the ISO string [toStorable]
  /// wrote. Both are the same instant, and last-write-wins has to be able
  /// to compare them — reading only one of the two shapes is what made
  /// `localTime` permanently null and the comparison a no-op.
  ///
  /// A value it cannot read is `null`, which the callers treat as "no
  /// local write to defend", so an unparseable timestamp costs a
  /// conflict rather than an exception.
  @visibleForTesting
  static DateTime? syncedAt(Map<dynamic, dynamic>? data) {
    final raw = data?['synced_at'];
    if (raw is Timestamp) return raw.toDate().toUtc();
    if (raw is DateTime) return raw.toUtc();
    if (raw is String) return DateTime.tryParse(raw)?.toUtc();
    return null;
  }

  /// Whether the server's copy should overwrite the local one.
  ///
  /// Ties go to the server, as before: a document written and immediately
  /// read back has the same stamp on both sides, and treating that as a
  /// conflict would leave the local copy holding the pre-resolution value
  /// forever.
  @visibleForTesting
  static bool serverWins(
    Map<dynamic, dynamic> serverData,
    Map<dynamic, dynamic>? localData,
  ) {
    final serverTime = syncedAt(serverData);
    if (serverTime == null) return false;
    final localTime = syncedAt(localData);
    return localTime == null || !serverTime.isBefore(localTime);
  }

  // ────────────────────────────────────────────────────────────────────────────
  // INITIALIZATION
  // ────────────────────────────────────────────────────────────────────────────

  /// Initialize Firestore and start connectivity listener
  static Future<void> init() async {
    if (_initialized) return;

    _db = FirebaseFirestore.instance;
    _db!.settings = const Settings(
      persistenceEnabled: true,
      cacheSizeBytes: Settings.CACHE_SIZE_UNLIMITED,
    );

    // Listen for connectivity changes
    _connectivitySubscription = _connectivity.onConnectivityChanged.listen(
      _onConnectivityChanged,
    );

    // Initial connectivity check
    final results = await _connectivity.checkConnectivity();
    _onConnectivityChanged(results);

    _initialized = true;
    debugPrint('FirestoreService: initialized with offline persistence');
  }

  static void _onConnectivityChanged(List<ConnectivityResult> results) {
    final isOnline = results.any((r) => r != ConnectivityResult.none);

    if (isOnline) {
      _setOnline();
      // Trigger sync for current user
      final uid = LocalStorageService.currentUserId;
      if (uid != null && LocalStorageService.cloudSyncEnabled) {
        flushPendingQueue(uid);
        syncCycleLogs(userId: uid);
        syncProfile(userId: uid);
      }
    } else {
      _setOffline();
    }
  }

  // ────────────────────────────────────────────────────────────────────────────
  // CYCLE LOGS SYNC
  // ────────────────────────────────────────────────────────────────────────────

  /// Push local cycle logs to Firestore (last-write-wins via server timestamp)
  static Future<void> syncCycleLogs({required String userId}) async {
    if (!LocalStorageService.cloudSyncEnabled) {
      debugPrint('FirestoreService: cloud sync disabled, skipping cycle sync');
      _updateStatus(SyncStatus.synced, 'cycle');
      return;
    }
    if (_db == null || _isSyncing) return;

    final logs = LocalStorageService.getCycleLogs();
    if (logs.isEmpty) {
      debugPrint('FirestoreService: no local cycle logs to sync');
      _updateStatus(SyncStatus.synced, 'cycle');
      return;
    }

    _isSyncing = true;
    _updateStatus(SyncStatus.syncing, 'cycle');

    try {
      final userRef = _db!.collection('client_sync').doc(userId);
      final deviceId = await LocalStorageService.deviceId();

      try {
        final batch = _db!.batch();

        for (final log in logs) {
          final docRef =
              userRef.collection('cycle_logs').doc(log['start_date'] as String);
          final data = Map<String, dynamic>.from(log);
          // Add server timestamp for conflict resolution
          data['synced_at'] = FieldValue.serverTimestamp();
          data['device_id'] = deviceId;
          batch.set(docRef, data, SetOptions(merge: true));
        }

        await batch.commit();
        debugPrint(
            'FirestoreService: synced ${logs.length} cycle logs for $userId');
      } catch (e) {
        debugPrint('FirestoreService: cycle sync failed: $e');
        _updateStatus(SyncStatus.error, 'cycle', error: e.toString());
        // Queue for retry
        await _queuePendingCycleLogs(userId, logs);
        return;
      }

      // Read back resolved server timestamps and update Hive.
      //
      // In its own try, and deliberately. The batch has committed by this
      // point, so the data *is* on the server; a failure here is a local
      // caching problem, and re-queuing the whole history for it — which
      // is what used to happen, because the write-back threw on every
      // document — meant the queue was refilled by the very sync that had
      // just emptied it, on every launch, forever (issue #550).
      try {
        for (final log in logs) {
          final docRef =
              userRef.collection('cycle_logs').doc(log['start_date'] as String);
          final doc = await docRef.get();
          if (doc.exists) {
            final resolvedData = toStorable(doc.data()!);
            resolvedData['start_date'] = log['start_date'];
            await LocalStorageService.saveCycleLog(resolvedData);
          }
        }
      } catch (e) {
        // The local copies keep their previous `synced_at`, so the next
        // pull sees the server as newer and reconciles then.
        debugPrint('FirestoreService: cycle sync write-back failed: $e');
      }

      _updateStatus(SyncStatus.synced, 'cycle');
    } finally {
      // In a `finally` so that no path — including one that throws before
      // the batch is built — can leave the flag set and make every later
      // `syncCycleLogs` a silent no-op.
      _isSyncing = false;
    }
  }

  /// Fetch cycle logs from Firestore and merge into local Hive (last-write-wins)
  static Future<void> pullCycleLogs(
      {required String userId, int limit = 50}) async {
    if (!LocalStorageService.cloudSyncEnabled) return;
    if (_db == null) return;

    try {
      final snapshot = await _db!
          .collection('client_sync')
          .doc(userId)
          .collection('cycle_logs')
          .orderBy('start_date', descending: true)
          .limit(limit)
          .get();

      for (final doc in snapshot.docs) {
        // Per-document, so one unreadable log costs one log. This loop
        // used to abort on the first document it touched — the write
        // below threw for every one of them — so a pull merged nothing
        // at all (issue #550).
        try {
          final data = doc.data();
          final localLog =
              LocalStorageService.getCycleLogForDate(DateTime.parse(doc.id));

          if (serverWins(data, localLog)) {
            final storable = toStorable(data);
            storable['start_date'] = doc.id; // Ensure start_date is present
            await LocalStorageService.saveCycleLog(storable);
          }
        } catch (e) {
          debugPrint(
              'FirestoreService: could not merge cycle log ${doc.id}: $e');
        }
      }
      debugPrint(
          'FirestoreService: pulled ${snapshot.docs.length} cycle logs for $userId');
      _updateStatus(SyncStatus.synced, 'cycle');
    } catch (e) {
      debugPrint('FirestoreService: pull cycle logs failed: $e');
      _updateStatus(SyncStatus.error, 'cycle', error: e.toString());
    }
  }

  /// Queue cycle logs for retry when offline
  static Future<void> _queuePendingCycleLogs(
      String userId, List<Map<String, dynamic>> logs) async {
    final pendingBox = await Hive.openBox<Map>('pending_cycle_sync');
    for (final log in logs) {
      final key = 'cycle::$userId::${log['start_date']}';
      await pendingBox.put(key, {
        ...log,
        'type': 'cycle',
        'user_id': userId,
        'queued_at': DateTime.now().toIso8601String()
      });
    }
    _updateStatus(SyncStatus.pending, 'cycle');
  }

  /// Queue a failed profile sync for retry when connectivity is restored
  static Future<void> _queuePendingProfile(
      String userId, Map<String, dynamic> profile) async {
    final pendingBox = await Hive.openBox<Map>('pending_cycle_sync');
    final key = 'profile::$userId';
    await pendingBox.put(key, {
      ...profile,
      'type': 'profile',
      'user_id': userId,
      'queued_at': DateTime.now().toIso8601String()
    });
    _updateStatus(SyncStatus.pending, 'profile');
  }

  /// Flush pending cycle logs and profile queue to Firestore
  static Future<void> flushPendingQueue(String userId) async {
    if (!LocalStorageService.cloudSyncEnabled) return;
    if (_db == null) return;

    final pendingBox = await Hive.openBox<Map>('pending_cycle_sync');
    final keys = pendingBox.keys
        .where((k) => k.toString().contains('::$userId'))
        .toList();

    if (keys.isEmpty) return;

    debugPrint(
        'FirestoreService: flushing ${keys.length} pending items for $userId');

    final deviceId = await LocalStorageService.deviceId();

    // Process cycle log entries (new keys start with 'cycle::',
    // old keys from before generalization have no prefix)
    final cycleKeys = keys.where((k) => !k.startsWith('profile::')).toList();
    if (cycleKeys.isNotEmpty) {
      _updateStatus(SyncStatus.syncing, 'cycle');
      try {
        final batch = _db!.batch();
        final userRef = _db!.collection('client_sync').doc(userId);

        for (final key in cycleKeys) {
          final log = pendingBox.get(key)!;
          if (log['type'] != 'cycle') continue;
          final docRef =
              userRef.collection('cycle_logs').doc(log['start_date'] as String);
          final data = Map<String, dynamic>.from(log);
          data.remove('type');
          data.remove('user_id');
          data.remove('queued_at');
          data['synced_at'] = FieldValue.serverTimestamp();
          data['device_id'] = deviceId;
          batch.set(docRef, data, SetOptions(merge: true));
        }

        await batch.commit();

        for (final key in cycleKeys) {
          await pendingBox.delete(key);
        }

        debugPrint(
            'FirestoreService: flushed ${cycleKeys.length} pending cycle logs for $userId');
        _updateStatus(SyncStatus.synced, 'cycle');
      } catch (e) {
        debugPrint('FirestoreService: flush cycle queue failed: $e');
        _updateStatus(SyncStatus.error, 'cycle', error: e.toString());
      }
    }

    // Process profile entry
    final profileKey = 'profile::$userId';
    if (keys.contains(profileKey)) {
      _updateStatus(SyncStatus.syncing, 'profile');
      try {
        final profileData = pendingBox.get(profileKey)!;
        final userRef = _db!.collection('client_sync').doc(userId);
        final data = Map<String, dynamic>.from(profileData);
        data.remove('type');
        data.remove('user_id');
        data.remove('queued_at');
        data['synced_at'] = FieldValue.serverTimestamp();
        data['device_id'] = deviceId;

        await userRef.set(data, SetOptions(merge: true));

        await pendingBox.delete(profileKey);

        debugPrint('FirestoreService: flushed pending profile for $userId');
        _updateStatus(SyncStatus.synced, 'profile');
      } catch (e) {
        debugPrint('FirestoreService: flush profile queue failed: $e');
        _updateStatus(SyncStatus.error, 'profile', error: e.toString());
      }
    }
  }

  // ────────────────────────────────────────────────────────────────────────────
  // PROFILE SYNC
  // ────────────────────────────────────────────────────────────────────────────

  /// Push local profile to Firestore
  static Future<void> syncProfile({required String userId}) async {
    if (!LocalStorageService.cloudSyncEnabled) return;
    if (_db == null) return;

    final profile = LocalStorageService.getProfile();
    if (profile == null) return;

    _updateStatus(SyncStatus.syncing, 'profile');

    final userRef = _db!.collection('client_sync').doc(userId);

    try {
      final data = Map<String, dynamic>.from(profile);
      data['synced_at'] = FieldValue.serverTimestamp();
      data['device_id'] = await LocalStorageService.deviceId();

      await userRef.set(data, SetOptions(merge: true));
      debugPrint('FirestoreService: synced profile for $userId');
    } catch (e) {
      debugPrint('FirestoreService: profile sync failed: $e');
      _updateStatus(SyncStatus.error, 'profile', error: e.toString());
      await _queuePendingProfile(userId, profile);
      return;
    }

    // Read back resolved server timestamp and update Hive. Split from the
    // push for the same reason as in `syncCycleLogs`: the write has
    // landed, so a failure here must not queue the profile for a retry of
    // something that already happened.
    try {
      final resolvedDoc = await userRef.get();
      if (resolvedDoc.exists) {
        await LocalStorageService.saveProfile(
          toStorable({...profile, ...resolvedDoc.data()!}),
        );
      }
    } catch (e) {
      debugPrint('FirestoreService: profile write-back failed: $e');
    }

    _updateStatus(SyncStatus.synced, 'profile');
  }

  /// Fetch profile from Firestore and merge into local Hive
  static Future<void> pullProfile({required String userId}) async {
    if (!LocalStorageService.cloudSyncEnabled) return;
    if (_db == null) return;

    try {
      final doc = await _db!.collection('client_sync').doc(userId).get();
      if (!doc.exists) return;

      final data = doc.data()!;
      final localProfile = LocalStorageService.getProfile() ?? {};

      // Last-write-wins based on synced_at timestamp. Both sides are read
      // through `syncedAt`, because the local copy holds the ISO string
      // `toStorable` wrote and the server's holds a `Timestamp` — reading
      // only the second shape made `localTime` permanently null and the
      // server the unconditional winner (issue #550).
      if (serverWins(data, localProfile)) {
        // Server is newer - merge server data into local (preserve local-only fields)
        await LocalStorageService.saveProfile(
          toStorable({...localProfile, ...data}),
        );
      }

      debugPrint('FirestoreService: pulled profile for $userId');
      _updateStatus(SyncStatus.synced, 'profile');
    } catch (e) {
      debugPrint('FirestoreService: pull profile failed: $e');
      _updateStatus(SyncStatus.error, 'profile', error: e.toString());
    }
  }

  // ────────────────────────────────────────────────────────────────────────────
  // REAL-TIME LISTENERS (optional - for live sync indicator)
  // ────────────────────────────────────────────────────────────────────────────

  /// Stream of cycle logs from Firestore for real-time updates
  static Stream<QuerySnapshot<Map<String, dynamic>>> cycleLogsStream(
      String userId) {
    if (_db == null) return Stream.empty();
    return _db!
        .collection('client_sync')
        .doc(userId)
        .collection('cycle_logs')
        .orderBy('start_date', descending: true)
        .limit(50)
        .snapshots();
  }

  /// Stream of profile from Firestore
  static Stream<DocumentSnapshot<Map<String, dynamic>>> profileStream(
      String userId) {
    if (_db == null) return Stream.empty();
    return _db!.collection('client_sync').doc(userId).snapshots();
  }

  // ────────────────────────────────────────────────────────────────────────────
  // CLEANUP
  // ────────────────────────────────────────────────────────────────────────────

  static void dispose() {
    _connectivitySubscription?.cancel();
  }
}
