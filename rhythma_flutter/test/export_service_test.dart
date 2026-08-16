import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/services/local_storage_service.dart';
import 'package:rhythma/services/export_service.dart';
import 'test_helpers/local_storage_fixture.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('test-user');
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  group('ExportService', () {
    test('builds export data with profile, contacts, and cycle logs', () async {
      await LocalStorageService.saveProfile({
        'name': 'Priya',
        'age': 28,
        'cycle_length': 28,
        'language': 'en',
      });
      await LocalStorageService.saveEmergencyContacts([
        {'name': 'Mother', 'phone': '+919876543210'},
      ]);
      await LocalStorageService.saveCycleLog({
        'start_date': '2025-10-01',
        'flow_intensity': 'Medium',
      });

      final jsonString = ExportService.buildExportJson();
      final data = jsonDecode(jsonString) as Map<String, dynamic>;

      expect(data.containsKey('export_date'), isTrue);
      expect(data.containsKey('profile'), isTrue);
      expect(data.containsKey('emergency_contacts'), isTrue);
      expect(data.containsKey('cycle_logs'), isTrue);

      final profile = data['profile'] as Map<String, dynamic>;
      expect(profile['name'], 'Priya');
      expect(profile['age'], 28);

      final contacts = data['emergency_contacts'] as List;
      expect(contacts.length, 1);
      expect(contacts[0]['name'], 'Mother');

      final logs = data['cycle_logs'] as List;
      expect(logs.length, 1);
      expect(logs[0]['start_date'], '2025-10-01');
    });

    test('handles empty profile and contacts gracefully', () async {
      final jsonString = ExportService.buildExportJson();
      final data = jsonDecode(jsonString) as Map<String, dynamic>;

      expect(data['profile'], isEmpty);
      expect(data['emergency_contacts'], isEmpty);
      expect(data['cycle_logs'], isEmpty);
    });

    test('generates valid JSON with all expected top-level keys', () async {
      final jsonString = ExportService.buildExportJson();
      final data = jsonDecode(jsonString) as Map<String, dynamic>;

      for (final key in ['export_date', 'profile', 'emergency_contacts', 'cycle_logs']) {
        expect(data.containsKey(key), isTrue);
      }
    });
  });
}
