import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/services/local_storage_service.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    FlutterSecureStorage.setMockInitialValues({});

    tempDir = await Directory.systemTemp.createTemp('hive_test_dir');
    Hive.init(tempDir.path);
  });

  tearDown(() async {
    LocalStorageService.testReset();
    await Hive.close();
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  test('Migration transparently encrypts unencrypted data', () async {
    final unencryptedCycleBox = await Hive.openBox<Map>('cycle_logs');
    final unencryptedUserBox = await Hive.openBox<Map>('user_profile');

    await unencryptedCycleBox.put('2025-10-01', {'start_date': '2025-10-01', 'flow': 'heavy'});
    await unencryptedUserBox.put('profile', {'name': 'Test User', 'age': 25});

    await unencryptedCycleBox.close();
    await unencryptedUserBox.close();

    await LocalStorageService.init(testPath: tempDir.path);

    const secureStorage = FlutterSecureStorage();
    final keyString = await secureStorage.read(key: 'hive_key');
    expect(keyString, isNotNull, reason: 'Encryption key should have been generated');

    final profile = LocalStorageService.getProfile();
    expect(profile?['name'], 'Test User');
    expect(profile?['age'], 25);

    final cycleBox = Hive.box<Map>('cycle_logs');
    expect(cycleBox.get('2025-10-01')?['flow'], 'heavy');

    await Hive.close();

    final cycleBoxFile = File('${tempDir.path}/cycle_logs.hive');
    final rawBytes = await cycleBoxFile.readAsBytes();
    final rawString = String.fromCharCodes(rawBytes);
    expect(rawString, isNot(contains('heavy')),
        reason: 'Encrypted file should not contain plaintext "heavy"');
    expect(rawString, isNot(contains('Test User')),
        reason: 'Encrypted file should not contain plaintext "Test User"');
  });

  test('offline_queue and pending_cycle_sync boxes are encrypted', () async {
    final offlineBox = await Hive.openBox<Map>('offline_queue');
    final pendingBox = await Hive.openBox<Map>('pending_cycle_sync');

    await offlineBox.put('upsert::user1::2025-10-01', {
      'type': 'upsert',
      'date_key': '2025-10-01',
      'payload': {'flow_intensity': 'heavy', 'mood': 'happy'},
      'user_id': 'user1',
    });
    await pendingBox.put('cycle::user1::2025-10-01', {
      'type': 'cycle',
      'start_date': '2025-10-01',
      'flow_intensity': 'light',
      'user_id': 'user1',
    });

    await offlineBox.close();
    await pendingBox.close();

    await LocalStorageService.init(testPath: tempDir.path);

    final migratedOffline = Hive.box<Map>('offline_queue');
    final migratedPending = Hive.box<Map>('pending_cycle_sync');

    final offlineEntry = migratedOffline.get('upsert::user1::2025-10-01');
    expect(offlineEntry, isNotNull);
    expect(offlineEntry?['type'], 'upsert');

    final pendingEntry = migratedPending.get('cycle::user1::2025-10-01');
    expect(pendingEntry, isNotNull);
    expect(pendingEntry?['type'], 'cycle');

    await Hive.close();

    final offlineFile = File('${tempDir.path}/offline_queue.hive');
    if (offlineFile.existsSync()) {
      final rawBytes = await offlineFile.readAsBytes();
      final rawString = String.fromCharCodes(rawBytes);
      expect(rawString, isNot(contains('flow_intensity')),
          reason: 'Offline queue values should be encrypted');
    }

    final pendingFile = File('${tempDir.path}/pending_cycle_sync.hive');
    if (pendingFile.existsSync()) {
      final rawBytes = await pendingFile.readAsBytes();
      final rawString = String.fromCharCodes(rawBytes);
      expect(rawString, isNot(contains('flow_intensity')),
          reason: 'Pending sync values should be encrypted');
    }
  });

  test('settings box is encrypted with sensitive data', () async {
    final settingsBox = await Hive.openBox<dynamic>('settings');

    await settingsBox.put('user1::chat_history', [
      {'role': 'user', 'content': 'My period is late'},
    ]);
    await settingsBox.put('user1::emergency_contacts', [
      {'name': 'Mom', 'phone': '+919876543210'},
    ]);
    await settingsBox.put('user1::dashboard_cache', {
      'average_cycle_length': 28,
    });
    await settingsBox.put('language', 'en');

    await settingsBox.close();

    await LocalStorageService.init(testPath: tempDir.path);

    final migratedSettings = Hive.box<dynamic>('settings');

    final chatHistory = migratedSettings.get('user1::chat_history');
    expect(chatHistory, isNotNull);
    expect((chatHistory as List).first['content'], 'My period is late');

    final emergencyContacts = migratedSettings.get('user1::emergency_contacts');
    expect(emergencyContacts, isNotNull);

    final dashboardCache = migratedSettings.get('user1::dashboard_cache');
    expect(dashboardCache, isNotNull);

    final language = migratedSettings.get('language');
    expect(language, 'en');

    await Hive.close();

    final settingsFile = File('${tempDir.path}/settings.hive');
    if (settingsFile.existsSync()) {
      final rawBytes = await settingsFile.readAsBytes();
      final rawString = String.fromCharCodes(rawBytes);
      expect(rawString, isNot(contains('My period is late')),
          reason: 'Settings values should be encrypted');
      expect(rawString, isNot(contains('+919876543210')),
          reason: 'Settings values should be encrypted');
    }
  });

  test('cipher is available after init', () async {
    expect(LocalStorageService.cipher, isNull);

    await LocalStorageService.init(testPath: tempDir.path);

    expect(LocalStorageService.cipher, isNotNull);
  });
}
