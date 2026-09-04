import 'dart:io';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/services/firestore_service.dart';
import 'package:rhythma/services/local_storage_service.dart';

import '../test_helpers/local_storage_fixture.dart';

/// Cloud sync never completed, because every write-back threw (issue #550).
///
/// `FirestoreService` takes documents straight off Firestore and hands
/// them to `LocalStorageService`, which puts them in Hive. Hive encodes
/// `int`, `double`, `bool`, `String`, `List`, `Map`, `DateTime` and
/// `Uint8List`, plus anything with a registered `TypeAdapter` — and this
/// app registers none. Every synced document carries a `Timestamp` under
/// `synced_at`, so the very first `saveCycleLog` threw
///
///     HiveError: Cannot write, unknown type: Timestamp.
///
/// `syncCycleLogs` caught it, marked the sync failed and re-queued the
/// whole history — which the next flush pushed again and the next sync
/// re-queued again. `pullCycleLogs` aborted on its first document.
///
/// The first test in this file is the bug itself, asserted against a real
/// Hive box rather than a mock: a mocked box that accepted a `Timestamp`
/// would have made every other test here pass while production kept
/// throwing. It is worth reading before the rest.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('user-1');
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  final at = Timestamp.fromDate(DateTime.utc(2026, 5, 13, 9, 30));
  final earlier = Timestamp.fromDate(DateTime.utc(2026, 5, 12, 9, 30));

  group('Hive cannot store what Firestore returns', () {
    test('a raw Firestore document throws on the way into Hive', () async {
      final box = Hive.box<Map>('cycle_logs');

      // Caught by hand rather than with `throwsA`, because Hive serialises
      // inside the Future `put` returns — whether the error surfaces
      // synchronously or asynchronously is an implementation detail this
      // test should not depend on.
      Object? caught;
      try {
        await box.put('user-1::2026-05-13', {
          'start_date': '2026-05-13',
          'synced_at': at,
        });
      } catch (error) {
        caught = error;
      }

      expect(
        caught,
        isA<HiveError>(),
        reason: 'if this stops throwing, the conversion below is unnecessary',
      );
    });

    test('the same document goes in once converted', () async {
      await LocalStorageService.saveCycleLog(
        FirestoreService.toStorable({
          'start_date': '2026-05-13',
          'flow_intensity': 'medium',
          'synced_at': at,
        }),
      );

      final stored = LocalStorageService.getCycleLogForDate(
        DateTime.utc(2026, 5, 13),
      );
      expect(stored, isNotNull);
      expect(stored!['flow_intensity'], 'medium');
      expect(stored['synced_at'], at.toDate().toUtc().toIso8601String());
    });
  });

  group('toStorable', () {
    test('converts a Timestamp to an ISO-8601 string', () {
      final converted = FirestoreService.toStorable({'synced_at': at});
      expect(converted['synced_at'], '2026-05-13T09:30:00.000Z');
    });

    test('converts a DateTime the same way', () {
      final converted = FirestoreService.toStorable({
        'synced_at': DateTime.utc(2026, 5, 13, 9, 30),
      });
      expect(converted['synced_at'], '2026-05-13T09:30:00.000Z');
    });

    test('normalises a local DateTime to UTC', () {
      final local = DateTime(2026, 5, 13, 9, 30);
      final converted = FirestoreService.toStorable({'synced_at': local});
      expect(converted['synced_at'], local.toUtc().toIso8601String());
    });

    test('leaves values Hive already understands alone', () {
      final converted = FirestoreService.toStorable({
        'start_date': '2026-05-13',
        'sleep_hours': 7.5,
        'stress_level': 3,
        'cycle_regular': true,
        'symptoms': ['cramps', 'headache'],
        'notes': null,
      });

      expect(converted['start_date'], '2026-05-13');
      expect(converted['sleep_hours'], 7.5);
      expect(converted['stress_level'], 3);
      expect(converted['cycle_regular'], isTrue);
      expect(converted['symptoms'], ['cramps', 'headache']);
      expect(converted['notes'], isNull);
    });

    test('reaches a Timestamp nested in a map', () {
      final converted = FirestoreService.toStorable({
        'meta': {'synced_at': at},
      });
      expect(
        (converted['meta'] as Map)['synced_at'],
        '2026-05-13T09:30:00.000Z',
      );
    });

    test('reaches a Timestamp nested in a list', () {
      final converted = FirestoreService.toStorable({
        'history': [at, 'plain'],
      });
      expect((converted['history'] as List).first, '2026-05-13T09:30:00.000Z');
      expect((converted['history'] as List).last, 'plain');
    });

    test('a converted nested structure is itself storable', () async {
      final box = Hive.box<Map>('cycle_logs');

      await box.put(
        'user-1::nested',
        FirestoreService.toStorable({
          'meta': {'synced_at': at},
          'history': [at],
        }),
      );

      final stored = box.get('user-1::nested');
      expect(stored, isNotNull);
      expect((stored!['meta'] as Map)['synced_at'], isA<String>());
      expect((stored['history'] as List).single, isA<String>());
    });
  });

  group('syncedAt reads both shapes', () {
    test('reads a Timestamp, as it arrives from Firestore', () {
      expect(FirestoreService.syncedAt({'synced_at': at}), at.toDate().toUtc());
    });

    test('reads the ISO string, as it comes back out of Hive', () {
      final stored = FirestoreService.toStorable({'synced_at': at});
      expect(FirestoreService.syncedAt(stored), at.toDate().toUtc());
    });

    test('a Timestamp and its stored form resolve to the same instant', () {
      final stored = FirestoreService.toStorable({'synced_at': at});
      expect(
        FirestoreService.syncedAt(stored),
        FirestoreService.syncedAt({'synced_at': at}),
      );
    });

    test('returns null for a missing, null or unreadable value', () {
      expect(FirestoreService.syncedAt(null), isNull);
      expect(FirestoreService.syncedAt({}), isNull);
      expect(FirestoreService.syncedAt({'synced_at': null}), isNull);
      expect(FirestoreService.syncedAt({'synced_at': 'not a date'}), isNull);
      expect(FirestoreService.syncedAt({'synced_at': 12345}), isNull);
    });
  });

  group('last-write-wins actually compares two writes', () {
    test('a newer local write is not overwritten', () {
      // The case that could never happen before: the local half of the
      // comparison was read out of Hive, where a Timestamp had never been
      // storable, so `localTime` was always null and the server always won.
      final local = FirestoreService.toStorable({'synced_at': at});
      expect(FirestoreService.serverWins({'synced_at': earlier}, local), isFalse);
    });

    test('a newer server write does overwrite', () {
      final local = FirestoreService.toStorable({'synced_at': earlier});
      expect(FirestoreService.serverWins({'synced_at': at}, local), isTrue);
    });

    test('a tie goes to the server', () {
      // A document written and immediately read back has the same stamp on
      // both sides; treating that as a conflict would leave the local copy
      // holding its pre-resolution value forever.
      final local = FirestoreService.toStorable({'synced_at': at});
      expect(FirestoreService.serverWins({'synced_at': at}, local), isTrue);
    });

    test('the server wins when there is no local copy', () {
      expect(FirestoreService.serverWins({'synced_at': at}, null), isTrue);
    });

    test('an unstamped server document never wins', () {
      final local = FirestoreService.toStorable({'synced_at': earlier});
      expect(FirestoreService.serverWins({'flow_intensity': 'light'}, local), isFalse);
    });
  });

  group('device id', () {
    test('is stable across calls', () async {
      final first = await LocalStorageService.deviceId();
      final second = await LocalStorageService.deviceId();

      expect(first, isNotEmpty);
      expect(second, first);
    });

    test('is not the user id', () async {
      // The bug it replaces: every synced document was stamped with
      // `currentUserId`, so two devices on one account were
      // indistinguishable and the field carried no information for the
      // conflict resolution it was added for.
      final id = await LocalStorageService.deviceId();
      expect(id, isNot(LocalStorageService.currentUserId));
    });

    test('does not change when the signed-in account does', () async {
      final first = await LocalStorageService.deviceId();

      await LocalStorageService.setCurrentUserId('user-2');

      expect(await LocalStorageService.deviceId(), first);
    });
  });
}
