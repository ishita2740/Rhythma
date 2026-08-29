import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/services/local_storage_service.dart';

import '../test_helpers/local_storage_fixture.dart';

/// Issue #521.
///
/// `LocalStorageService` namespaces cycle logs, the profile, chat history
/// and `onboardingCompleted` by user id. Six settings were read straight
/// off the bare key, so on a shared phone they were not "kept for the
/// previous account" — they were inherited by the next one.
///
/// The scenario throughout is the one the README describes as ordinary for
/// this app's users: one phone, more than one woman.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  /// The raw settings box, for asserting what is at the device level.
  Box<dynamic> settings() => Hive.box<dynamic>('settings');

  Future<void> signIn(String uid) => LocalStorageService.setCurrentUserId(uid);
  Future<void> signOut() => LocalStorageService.setCurrentUserId(null);

  group('consent flags do not cross accounts', () {
    test('cloud sync enabled by one account is off for the next', () async {
      await signIn('asha');
      await LocalStorageService.setCloudSync(true);
      expect(LocalStorageService.cloudSyncEnabled, isTrue);

      await signOut();
      await signIn('priya');

      // Before the fix this was `true`, and `firestore_service` would have
      // started uploading Priya's cycle logs to Firestore from her first
      // entry without her ever being asked.
      expect(LocalStorageService.cloudSyncEnabled, isFalse);
    });

    test('the biometric lock does not follow the phone to a new account',
        () async {
      await signIn('asha');
      await LocalStorageService.setBiometricEnabled(true);

      await signOut();
      await signIn('priya');

      expect(LocalStorageService.biometricEnabled, isFalse);
    });

    test('SMS summaries do not follow the phone to a new account', () async {
      await signIn('asha');
      await LocalStorageService.setSmsEnabled(true);

      await signOut();
      await signIn('priya');

      expect(LocalStorageService.smsEnabled, isFalse);
    });

    test('one account turning a flag off does not turn it off for another',
        () async {
      // The inverse leak, and the one a user would never think to check:
      // her sync silently stops because someone else switched it off.
      await signIn('asha');
      await LocalStorageService.setCloudSync(true);

      await signOut();
      await signIn('priya');
      await LocalStorageService.setCloudSync(false);

      await signOut();
      await signIn('asha');

      expect(LocalStorageService.cloudSyncEnabled, isTrue);
    });

    test('each account keeps its own answer across several switches',
        () async {
      await signIn('asha');
      await LocalStorageService.setCloudSync(true);
      await LocalStorageService.setBiometricEnabled(true);

      await signOut();
      await signIn('priya');
      await LocalStorageService.setSmsEnabled(true);

      await signOut();
      await signIn('asha');
      expect(LocalStorageService.cloudSyncEnabled, isTrue);
      expect(LocalStorageService.biometricEnabled, isTrue);
      expect(LocalStorageService.smsEnabled, isFalse);

      await signOut();
      await signIn('priya');
      expect(LocalStorageService.cloudSyncEnabled, isFalse);
      expect(LocalStorageService.biometricEnabled, isFalse);
      expect(LocalStorageService.smsEnabled, isTrue);
    });

    test('a consent flag is never mirrored to the device level', () async {
      await signIn('asha');
      await LocalStorageService.setCloudSync(true);

      // The mechanism, asserted directly: a device-level copy is exactly
      // what the next account would find.
      expect(settings().containsKey('cloud_sync'), isFalse);
      expect(settings().get('asha::cloud_sync'), isTrue);
    });
  });

  group('upgrading an existing single-user install', () {
    test('the first account to sign in keeps the settings it had', () async {
      // With no account signed in, `_scoped` returns the bare key — which
      // is exactly the state a pre-fix install is in.
      await LocalStorageService.setCloudSync(true);
      await LocalStorageService.setBiometricEnabled(true);
      expect(settings().get('cloud_sync'), isTrue);

      await signIn('asha');

      expect(LocalStorageService.cloudSyncEnabled, isTrue);
      expect(LocalStorageService.biometricEnabled, isTrue);
    });

    test('and the device-level copy is cleared so nobody else inherits it',
        () async {
      await LocalStorageService.setCloudSync(true);

      await signIn('asha');
      expect(settings().containsKey('cloud_sync'), isFalse);

      await signOut();
      await signIn('priya');
      expect(LocalStorageService.cloudSyncEnabled, isFalse);
    });

    test('an account that already has its own value still clears the shared one',
        () async {
      // The adoption is guarded; the delete is not. An account with its own
      // answer must not leave the legacy key behind for the next person.
      await signIn('asha');
      await LocalStorageService.setCloudSync(false);
      await signOut();

      await settings().put('cloud_sync', true);
      await signIn('asha');

      expect(LocalStorageService.cloudSyncEnabled, isFalse);
      expect(settings().containsKey('cloud_sync'), isFalse);
    });
  });

  group('preferences stay device-level', () {
    test('a language chosen before sign-in survives signing in', () async {
      // `language_selection_screen` runs before there is an account to
      // attribute the choice to, so this must keep working.
      await LocalStorageService.setPreferredLanguage('bn');

      await signIn('asha');

      expect(LocalStorageService.preferredLanguage, 'bn');
    });

    test("a signed-in user's own choice wins over the device value", () async {
      await LocalStorageService.setPreferredLanguage('bn');
      await signIn('asha');
      await LocalStorageService.setPreferredLanguage('ta');

      expect(LocalStorageService.preferredLanguage, 'ta');
      expect(settings().get('asha::language'), 'ta');
    });

    test('and is mirrored so the login screen is not reset to English',
        () async {
      await signIn('asha');
      await LocalStorageService.setPreferredLanguage('ta');

      await signOut();

      expect(LocalStorageService.preferredLanguage, 'ta');
    });

    test('the theme falls back to the device value', () async {
      await LocalStorageService.setThemeMode('dark');
      await LocalStorageService.setPrimaryColor(0xFFE07AAD);

      await signIn('asha');

      expect(LocalStorageService.getThemeMode(), 'dark');
      expect(LocalStorageService.getPrimaryColor(), 0xFFE07AAD);
    });

    test('but an account that picked a theme keeps it', () async {
      await signIn('asha');
      await LocalStorageService.setThemeMode('dark');

      await signOut();
      await signIn('priya');
      await LocalStorageService.setThemeMode('light');

      await signOut();
      await signIn('asha');

      expect(LocalStorageService.getThemeMode(), 'dark');
    });

    test('the language defaults to English when nothing has been chosen',
        () async {
      await signIn('asha');
      expect(LocalStorageService.preferredLanguage, 'en');
    });
  });

  group('deleting an account', () {
    test('takes its consent flags with it', () async {
      await signIn('asha');
      await LocalStorageService.setCloudSync(true);
      await LocalStorageService.setBiometricEnabled(true);

      await LocalStorageService.deleteCurrentUserData();

      expect(settings().containsKey('asha::cloud_sync'), isFalse);
      expect(settings().containsKey('asha::biometric_enabled'), isFalse);
    });

    test('and leaves no device-level copy behind', () async {
      // The case where this account never went through the migration:
      // deleting it must still not leave an answer where the next person
      // to use the phone would inherit it.
      await settings().put('cloud_sync', true);
      await seedCurrentUserId('asha');

      await LocalStorageService.deleteCurrentUserData();

      expect(settings().containsKey('cloud_sync'), isFalse);
    });

    test('does not disturb another account', () async {
      await signIn('priya');
      await LocalStorageService.setCloudSync(true);
      await signOut();

      await signIn('asha');
      await LocalStorageService.setCloudSync(true);
      await LocalStorageService.deleteCurrentUserData();

      await signIn('priya');
      expect(LocalStorageService.cloudSyncEnabled, isTrue);
    });
  });
}
