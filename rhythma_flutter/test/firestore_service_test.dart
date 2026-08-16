import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/services/firestore_service.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    tempDir = await Directory.systemTemp.createTemp('firestore_test_dir');
    Hive.init(tempDir.path);
  });

  tearDown(() async {
    await Hive.close();
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  group('Null-safe stream getters', () {
    test(
        'cycleLogsStream returns empty stream when Firestore is not initialized',
        () async {
      final stream = FirestoreService.cycleLogsStream('test-user');
      final events = await stream.toList();
      expect(events, isEmpty);
    });

    test('profileStream returns empty stream when Firestore is not initialized',
        () async {
      final stream = FirestoreService.profileStream('test-user');
      final events = await stream.toList();
      expect(events, isEmpty);
    });

    test('cycleLogsStream does not throw when called without init', () {
      expect(
        () => FirestoreService.cycleLogsStream('test-user'),
        returnsNormally,
      );
    });

    test('profileStream does not throw when called without init', () {
      expect(
        () => FirestoreService.profileStream('test-user'),
        returnsNormally,
      );
    });
  });

  group('Profile retry queue', () {
    test('pending_cycle_sync box stores profile entries with correct fields',
        () async {
      final box = await Hive.openBox<Map>('pending_cycle_sync');
      const userId = 'user-123';
      final profile = {
        'name': 'Test User',
        'age': 25,
        'email': 'test@example.com',
      };

      await box.put('profile::$userId', {
        ...profile,
        'type': 'profile',
        'user_id': userId,
        'queued_at': DateTime.now().toIso8601String(),
      });

      final stored = box.get('profile::$userId');
      expect(stored, isNotNull);
      expect(stored!['type'], 'profile');
      expect(stored['user_id'], userId);
      expect(stored['name'], 'Test User');
      expect(stored['age'], 25);
      expect(stored['email'], 'test@example.com');
      expect(stored.containsKey('queued_at'), isTrue);
    });

    test('cycle and profile entries coexist in the same box', () async {
      final box = await Hive.openBox<Map>('pending_cycle_sync');
      const userId = 'user-123';

      // Store a cycle log entry
      await box.put('cycle::$userId::2025-01-15', {
        'start_date': '2025-01-15',
        'flow': 'medium',
        'type': 'cycle',
        'user_id': userId,
        'queued_at': DateTime.now().toIso8601String(),
      });

      // Store a profile entry
      await box.put('profile::$userId', {
        'name': 'Test',
        'type': 'profile',
        'user_id': userId,
        'queued_at': DateTime.now().toIso8601String(),
      });

      // Verify both can be retrieved
      final allKeys = box.keys.toList();
      expect(allKeys, contains('cycle::$userId::2025-01-15'));
      expect(allKeys, contains('profile::$userId'));

      // Verify type-based filtering
      final cycleKeys =
          allKeys.where((k) => !k.startsWith('profile::')).toList();
      expect(cycleKeys, contains('cycle::$userId::2025-01-15'));
      expect(cycleKeys, isNot(contains('profile::$userId')));

      const profileKey = 'profile::$userId';
      expect(allKeys, contains(profileKey));
    });
  });
}
