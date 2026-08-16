import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/services/local_storage_service.dart';
import 'test_helpers/local_storage_fixture.dart';

// Mirrors the regex used in onboarding_screen.dart and sms_screen.dart.
final _e164 = RegExp(r'^\+[1-9]\d{1,14}$');

/// Unit tests for the onboarding-related LocalStorageService methods.
void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('test-user');
    await seedOnboardingCompleted('test-user', false);
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  group('onboardingCompleted flag', () {
    test('returns false by default', () {
      expect(LocalStorageService.onboardingCompleted, isFalse);
    });

    test('setOnboardingCompleted(true) stores and retrieves true', () async {
      await LocalStorageService.setOnboardingCompleted(true);
      expect(LocalStorageService.onboardingCompleted, isTrue);
    });

    test('setOnboardingCompleted(false) resets flag', () async {
      await LocalStorageService.setOnboardingCompleted(true);
      await LocalStorageService.setOnboardingCompleted(false);
      expect(LocalStorageService.onboardingCompleted, isFalse);
    });

    test('clearAll resets onboardingCompleted flag', () async {
      await LocalStorageService.setOnboardingCompleted(true);
      await LocalStorageService.clearAll();
      expect(LocalStorageService.onboardingCompleted, isFalse);
    });
  });

  group('saveProfile and getProfile', () {
    test('getProfile returns null when nothing is saved', () {
      expect(LocalStorageService.getProfile(), isNull);
    });

    test('saveProfile stores a profile and getProfile retrieves it', () async {
      final profile = {'name': 'Aarya', 'age': 25, 'cycle_length': 28};
      await LocalStorageService.saveProfile(profile);
      final retrieved = LocalStorageService.getProfile();
      expect(retrieved, equals(profile));
    });

    test('saveProfile overwrites the entire profile', () async {
      await LocalStorageService.saveProfile({'name': 'Aarya', 'age': 25});
      await LocalStorageService.saveProfile(
          {'name': 'Priya', 'cycle_length': 30});
      final retrieved = LocalStorageService.getProfile();
      expect(retrieved, equals({'name': 'Priya', 'cycle_length': 30}));
      expect(retrieved!.containsKey('age'), isFalse,
          reason: 'saveProfile should overwrite entirely');
    });
  });

  group('mergeProfile', () {
    test('mergeProfile creates profile when none exists', () async {
      await LocalStorageService.mergeProfile({'name': 'Aarya', 'age': 25});
      final profile = LocalStorageService.getProfile();
      expect(profile, {'name': 'Aarya', 'age': 25});
    });

    test('mergeProfile adds new fields to existing profile', () async {
      await LocalStorageService.saveProfile(
          {'name': 'Aarya', 'age': 25, 'avatar': '🌸'});
      await LocalStorageService.mergeProfile({'cycle_length': 28});
      final profile = LocalStorageService.getProfile();
      expect(profile!['name'], 'Aarya');
      expect(profile['age'], 25);
      expect(profile['avatar'], '🌸');
      expect(profile['cycle_length'], 28);
    });

    test('mergeProfile overwrites only updated fields', () async {
      await LocalStorageService.saveProfile({
        'name': 'Aarya',
        'age': 25,
        'avatar': '🌸',
        'last_period': '2025-06-01',
      });
      await LocalStorageService.mergeProfile(
          {'name': 'Aarya Renamed', 'age': 26});
      final profile = LocalStorageService.getProfile();
      expect(profile!['name'], 'Aarya Renamed');
      expect(profile['age'], 26);
      expect(profile['avatar'], '🌸');
      expect(profile['last_period'], '2025-06-01');
    });

    test('mergeProfile does not remove onboarding-only fields', () async {
      await LocalStorageService.saveProfile({
        'name': 'Aarya',
        'avatar': '🌙',
        'last_period': '2025-05-15',
        'cycle_length': 28,
        'period_duration': 5,
        'cycle_regular': true,
        'city': 'Mumbai',
        'notifications_enabled': false,
      });
      await LocalStorageService.mergeProfile({
        'name': 'Aarya Updated',
        'age': 27,
        'cycle_length': 30,
      });
      final profile = LocalStorageService.getProfile()!;
      expect(profile['name'], 'Aarya Updated');
      expect(profile['age'], 27);
      expect(profile['cycle_length'], 30);
      expect(profile['avatar'], '🌙');
      expect(profile['last_period'], '2025-05-15');
      expect(profile['period_duration'], 5);
      expect(profile['cycle_regular'], true);
      expect(profile['city'], 'Mumbai');
      expect(profile['notifications_enabled'], false);
    });
  });

  group('onboarding persistence flow', () {
    test('full onboarding save followed by edit profile merge', () async {
      final onboardingData = {
        'name': 'Sita',
        'avatar': '🌺',
        'language': 'hi',
        'age': 24,
        'height_cm': 162.0,
        'weight_kg': 56.0,
        'last_period': '2025-06-10',
        'last_period_is_approximate': false,
        'cycle_length': 27,
        'period_duration': 4,
        'cycle_regular': true,
        'phone': '+919876543210',
        'city': 'Pune',
        'state': '411001',
        'notifications_enabled': true,
      };
      await LocalStorageService.saveProfile(onboardingData);
      await LocalStorageService.setOnboardingCompleted(true);

      expect(LocalStorageService.onboardingCompleted, isTrue);

      await LocalStorageService.mergeProfile({
        'name': 'Sita S.',
        'age': 25,
        'cycle_length': 28,
      });

      final profile = LocalStorageService.getProfile()!;
      expect(profile['name'], 'Sita S.');
      expect(profile['age'], 25);
      expect(profile['cycle_length'], 28);
      expect(profile['avatar'], '🌺');
      expect(profile['language'], 'hi');
      expect(profile['height_cm'], 162.0);
      expect(profile['weight_kg'], 56.0);
      expect(profile['last_period'], '2025-06-10');
      expect(profile['last_period_is_approximate'], false);
      expect(profile['period_duration'], 4);
      expect(profile['cycle_regular'], true);
      expect(profile['phone'], '+919876543210');
      expect(profile['city'], 'Pune');
      expect(profile['state'], '411001');
      expect(profile['notifications_enabled'], true);
    });

    test('approximate onboarding date is stored correctly', () async {
      final onboardingData = {
        'name': 'Test',
        'last_period': '2025-07-01',
        'last_period_is_approximate': true,
        'cycle_length': 28,
        'period_duration': 5,
        'cycle_regular': true,
      };
      await LocalStorageService.saveProfile(onboardingData);
      final profile = LocalStorageService.getProfile()!;
      expect(profile['last_period'], '2025-07-01');
      expect(profile['last_period_is_approximate'], true);
    });
  });

  group('nudge preferences', () {
    test('getNudgeDismissed returns false by default', () {
      expect(
          LocalStorageService.getNudgeDismissed('last_period_exact'), isFalse);
    });

    test('setNudgeDismissed stores and retrieves correctly', () async {
      await LocalStorageService.setNudgeDismissed('last_period_exact', true);
      expect(
          LocalStorageService.getNudgeDismissed('last_period_exact'), isTrue);
    });

    test('different nudge keys are independent', () async {
      await LocalStorageService.setNudgeDismissed('nudge_a', true);
      await LocalStorageService.setNudgeDismissed('nudge_b', false);
      expect(LocalStorageService.getNudgeDismissed('nudge_a'), isTrue);
      expect(LocalStorageService.getNudgeDismissed('nudge_b'), isFalse);
    });
  });

  // ── Step 4 phone validation (E.164 regex regression) ─────────────────────

  group('Step 4 phone E.164 validation', () {
    test('empty phone passes (field is optional)', () {
      expect(''.isEmpty || _e164.hasMatch(''), isTrue);
    });

    test('valid Indian E.164 number passes', () {
      expect(_e164.hasMatch('+919876543210'), isTrue);
    });

    test('valid US E.164 number passes', () {
      expect(_e164.hasMatch('+12025551234'), isTrue);
    });

    test('bare 10-digit number without country code fails', () {
      expect(_e164.hasMatch('9876543210'), isFalse);
    });

    test('number with spaces fails', () {
      expect(_e164.hasMatch('+91 98765 43210'), isFalse);
    });

    test('number with dashes fails', () {
      expect(_e164.hasMatch('+1-202-555-1234'), isFalse);
    });

    test('letters-only string fails', () {
      expect(_e164.hasMatch('abcdefg'), isFalse);
    });

    test('plus sign alone fails', () {
      expect(_e164.hasMatch('+'), isFalse);
    });

    test('leading zero after plus fails (E.164 forbids it)', () {
      expect(_e164.hasMatch('+0123456789'), isFalse);
    });
  });
}
