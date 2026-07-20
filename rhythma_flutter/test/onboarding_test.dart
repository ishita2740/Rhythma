import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/services/local_storage_service.dart';

/// Unit tests for the onboarding-related LocalStorageService methods.
/// These tests use [LocalStorageService.isTesting] = true to avoid
/// opening real Hive boxes during testing.
void main() {
  setUp(() {
    LocalStorageService.isTesting = true;
    LocalStorageService.mockProfile = null;
    LocalStorageService.mockEmergencyContacts = [];
    LocalStorageService.mockOnboardingCompleted = false;
  });

  tearDown(() {
    LocalStorageService.isTesting = false;
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
      // Onboarding fields not in the update are preserved
      expect(profile['avatar'], '🌸');
      expect(profile['last_period'], '2025-06-01');
    });

    test('mergeProfile does not remove onboarding-only fields', () async {
      // Simulate onboarding save
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
      // Simulate Edit Profile update (only name + age + cycle_length)
      await LocalStorageService.mergeProfile({
        'name': 'Aarya Updated',
        'age': 27,
        'cycle_length': 30,
      });
      final profile = LocalStorageService.getProfile()!;
      expect(profile['name'], 'Aarya Updated');
      expect(profile['age'], 27);
      expect(profile['cycle_length'], 30);
      // All onboarding-only fields must still be present
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
      // Simulate completing onboarding
      final onboardingData = {
        'name': 'Sita',
        'avatar': '🌺',
        'language': 'hi',
        'age': 24,
        'height_cm': 162.0,
        'weight_kg': 56.0,
        'last_period': '2025-06-10',
        'cycle_length': 27,
        'period_duration': 4,
        'cycle_regular': true,
        'phone': '9876543210',
        'city': 'Pune',
        'state': '411001',
        'notifications_enabled': true,
      };
      await LocalStorageService.saveProfile(onboardingData);
      await LocalStorageService.setOnboardingCompleted(true);

      expect(LocalStorageService.onboardingCompleted, isTrue);

      // Later: user edits profile (only name + age + cycle_length)
      await LocalStorageService.mergeProfile({
        'name': 'Sita S.',
        'age': 25,
        'cycle_length': 28,
      });

      final profile = LocalStorageService.getProfile()!;
      expect(profile['name'], 'Sita S.');
      expect(profile['age'], 25);
      expect(profile['cycle_length'], 28);
      // All other fields preserved
      expect(profile['avatar'], '🌺');
      expect(profile['language'], 'hi');
      expect(profile['height_cm'], 162.0);
      expect(profile['weight_kg'], 56.0);
      expect(profile['last_period'], '2025-06-10');
      expect(profile['period_duration'], 4);
      expect(profile['cycle_regular'], true);
      expect(profile['phone'], '9876543210');
      expect(profile['city'], 'Pune');
      expect(profile['state'], '411001');
      expect(profile['notifications_enabled'], true);
    });
  });
}
