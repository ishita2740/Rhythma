import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/providers/profile_provider.dart';
import 'package:rhythma/services/auth_service.dart';
import 'package:rhythma/services/local_storage_service.dart';
import 'package:rhythma/services/profile_service.dart';
import 'package:rhythma/utils/secure_storage.dart';

import '../test_helpers/dio_mock_adapter.dart';
import '../test_helpers/local_storage_fixture.dart';

/// Onboarding data reaches the server, and the server does not overwrite
/// the handset (issue #551).
///
/// `_saveAndComplete` wrote Hive and stopped, with a comment saying a
/// background sync could be added later. There was no later. So the
/// server's user document had no `last_period`, no `cycle_length`, no age
/// and no name — and `/cycle/predictions`, `/dashboard`, the observations
/// and the SMS summary all fell back to a 28-day population default while
/// the cycle length the user had just declared sat unread on the handset.
/// A reinstall or a second device lost the lot.
///
/// The tests are grouped by the three things that had to change: the push
/// exists, a failed push is remembered rather than dropped, and the pull
/// merges instead of replacing.
///
/// They drive `validateSession()` — the real entry point, called on every
/// cold start — rather than the private method it delegates to, because
/// "what happens when the app launches" is the actual question.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('user-1');
    await SecureStorage.saveToken('valid-token');
  });

  tearDown(() async {
    await SecureStorage.clearAuth();
    restoreDioAdapter();
    await tearDownLocalStorage(tempDir);
  });

  /// The profile a user has just finished onboarding with.
  Map<String, dynamic> onboardingProfile() => {
        'name': 'Aarya',
        'avatar': 'assets/avatars/avatar_3.png',
        'language': 'hi',
        'age': 27,
        'last_period': '2026-05-01',
        'cycle_length': 31,
        'period_duration': 5,
        'cycle_regular': true,
      };

  Future<void> setNeedsPush(bool value) async {
    await Hive.box<dynamic>('settings').put('user-1::profile_needs_push', value);
  }

  bool needsPush() =>
      Hive.box<dynamic>('settings').get('user-1::profile_needs_push') as bool? ??
      false;

  group('patchProfile reports whether the server took it', () {
    test('true on a 2xx', () async {
      installMockDioAdapter((_) => const MockDioResponse(200, {'id': 'user-1'}));

      expect(await ProfileService.patchProfile({'cycle_length': 31}), isTrue);
    });

    test('false on a server error', () async {
      installMockDioAdapter((_) => const MockDioResponse(500));

      expect(await ProfileService.patchProfile({'cycle_length': 31}), isFalse);
    });

    test('true when there is nothing to send', () async {
      // Not a failure: there is no state on the server that disagrees with
      // the device, so reporting it as one would leave the flag set
      // forever.
      installMockDioAdapter((_) => const MockDioResponse(500));

      expect(await ProfileService.patchProfile({'unknown_key': 1}), isTrue);
    });
  });

  group('onboarding pushes what it collected', () {
    test('saveProfileWithSync sends the profile to the backend', () async {
      RequestOptions? patched;
      installMockDioAdapter((options) {
        if (options.path == '/auth/profile' && options.method == 'PATCH') {
          patched = options;
          return const MockDioResponse(200, {'id': 'user-1'});
        }
        return const MockDioResponse(404);
      });

      final accepted =
          await ProfileProvider().saveProfileWithSync(onboardingProfile());

      expect(accepted, isTrue);
      expect(patched, isNotNull);
      final body = patched!.data as Map;
      // The three the server-side predictions actually read.
      expect(body['cycle_length'], 31);
      expect(body['last_period'], '2026-05-01');
      expect(body['period_duration'], 5);
      // Hive calls it `name`; the backend calls it `full_name`.
      expect(body['full_name'], 'Aarya');
    });

    test('the profile is still saved locally when the push succeeds', () async {
      installMockDioAdapter((_) => const MockDioResponse(200, {'id': 'user-1'}));

      await ProfileProvider().saveProfileWithSync(onboardingProfile());

      expect(LocalStorageService.getProfile()?['cycle_length'], 31);
      expect(needsPush(), isFalse);
    });

    test('a failed push still saves locally and is remembered', () async {
      // The audience this app is for often has no connection at the moment
      // she finishes signing up. Losing the push is not acceptable, and
      // blocking on it would be worse.
      installMockDioAdapter((_) => const MockDioResponse(503));

      final accepted =
          await ProfileProvider().saveProfileWithSync(onboardingProfile());

      expect(accepted, isFalse);
      expect(LocalStorageService.getProfile()?['cycle_length'], 31);
      expect(needsPush(), isTrue);
    });
  });

  group('a launch sends what is still owed', () {
    test('validateSession pushes a profile the server never got', () async {
      await seedProfile('user-1', onboardingProfile());
      await setNeedsPush(true);

      var patchCount = 0;
      installMockDioAdapter((options) {
        if (options.path == '/auth/me') {
          return const MockDioResponse(200, {'id': 'user-1'});
        }
        if (options.path == '/auth/profile' && options.method == 'PATCH') {
          patchCount++;
          return const MockDioResponse(200, {'id': 'user-1'});
        }
        return const MockDioResponse(200, {'id': 'user-1'});
      });

      await AuthService().validateSession();

      expect(patchCount, 1);
      expect(needsPush(), isFalse);
    });

    test('a launch that cannot reach the server keeps owing it', () async {
      await seedProfile('user-1', onboardingProfile());
      await setNeedsPush(true);

      installMockDioAdapter((options) {
        if (options.path == '/auth/profile' && options.method == 'PATCH') {
          return const MockDioResponse(503);
        }
        return const MockDioResponse(200, {'id': 'user-1'});
      });

      await AuthService().validateSession();

      expect(needsPush(), isTrue);
    });

    test('nothing is pushed when nothing is owed', () async {
      await seedProfile('user-1', onboardingProfile());
      await setNeedsPush(false);

      var patchCount = 0;
      installMockDioAdapter((options) {
        if (options.path == '/auth/profile' && options.method == 'PATCH') {
          patchCount++;
        }
        return const MockDioResponse(200, {'id': 'user-1'});
      });

      await AuthService().validateSession();

      expect(patchCount, 0);
    });
  });

  group('the pull merges instead of replacing', () {
    test('a server document with no name does not rename the user', () async {
      // The old code built the local profile from a whitelist with
      // `profile['full_name'] ?? 'User'` and `saveProfile`d it, which
      // replaces. So every cold start renamed her to the literal string
      // "User" and reset her avatar to avatar_1.
      await seedProfile('user-1', {
        'name': 'Aarya',
        'avatar': 'assets/avatars/avatar_3.png',
      });
      await setNeedsPush(false);

      installMockDioAdapter((options) {
        if (options.path == '/auth/profile' && options.method == 'GET') {
          return const MockDioResponse(200, {'id': 'user-1', 'cycle_length': 31});
        }
        return const MockDioResponse(200, {'id': 'user-1'});
      });

      await AuthService().validateSession();

      final profile = LocalStorageService.getProfile()!;
      expect(profile['name'], 'Aarya');
      expect(profile['avatar'], 'assets/avatars/avatar_3.png');
      expect(profile['cycle_length'], 31);
    });

    test('local-only fields survive the merge', () async {
      await seedProfile('user-1', {'name': 'Aarya', 'notes_draft': 'keep me'});
      await setNeedsPush(false);

      installMockDioAdapter((options) {
        if (options.path == '/auth/profile' && options.method == 'GET') {
          return const MockDioResponse(
              200, {'id': 'user-1', 'full_name': 'Aarya K', 'age': 27});
        }
        return const MockDioResponse(200, {'id': 'user-1'});
      });

      await AuthService().validateSession();

      final profile = LocalStorageService.getProfile()!;
      expect(profile['notes_draft'], 'keep me');
      expect(profile['name'], 'Aarya K');
      expect(profile['age'], 27);
    });

    test('a server profile without a cycle length still syncs', () async {
      // The whole method used to be gated on `cycle_length != null`, so an
      // account whose server copy had none — which was every account,
      // given the missing push — synced nothing at all.
      await setNeedsPush(false);

      installMockDioAdapter((options) {
        if (options.path == '/auth/profile' && options.method == 'GET') {
          return const MockDioResponse(
              200, {'id': 'user-1', 'full_name': 'Aarya', 'city': 'Nagpur'});
        }
        return const MockDioResponse(200, {'id': 'user-1'});
      });

      await AuthService().validateSession();

      final profile = LocalStorageService.getProfile()!;
      expect(profile['name'], 'Aarya');
      expect(profile['city'], 'Nagpur');
    });

    test('a server cycle length still marks onboarding complete', () async {
      // The one thing that flag genuinely means: this account finished
      // onboarding somewhere. It is what makes a reinstall skip the five
      // screens instead of asking for everything again.
      await seedOnboardingCompleted('user-1', false);
      await setNeedsPush(false);

      installMockDioAdapter((options) {
        if (options.path == '/auth/profile' && options.method == 'GET') {
          return const MockDioResponse(200, {'id': 'user-1', 'cycle_length': 31});
        }
        return const MockDioResponse(200, {'id': 'user-1'});
      });

      await AuthService().validateSession();

      expect(LocalStorageService.onboardingCompleted, isTrue);
    });

    test('a server field that is absent does not clear the local one', () async {
      await seedProfile('user-1', {'name': 'Aarya', 'city': 'Nagpur'});
      await setNeedsPush(false);

      installMockDioAdapter((options) {
        if (options.path == '/auth/profile' && options.method == 'GET') {
          return const MockDioResponse(
              200, {'id': 'user-1', 'city': null, 'age': 27});
        }
        return const MockDioResponse(200, {'id': 'user-1'});
      });

      await AuthService().validateSession();

      expect(LocalStorageService.getProfile()?['city'], 'Nagpur');
    });
  });
}
