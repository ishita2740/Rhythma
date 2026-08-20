// The retry policy driven through the real interceptor (issue #500).
//
// `api_retry_test.dart` covers the decisions. This covers the wiring: that
// a retryable failure really is replayed, that a non-retryable one really
// is not, that the transient budget and the token-refresh budget stay
// separate, and that a refresh which fails in an unexpected way still ends
// with the user signed out rather than with a request that never settles.
//
// `ApiClient.retryPolicy` is replaced for the duration with one whose
// jitter is pinned to zero, so a test that exercises three attempts costs
// no wall-clock and cannot flake on timing.

import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/services/api_client.dart';
import 'package:rhythma/services/api_retry.dart';
import 'package:rhythma/utils/secure_storage.dart';

import '../test_helpers/dio_mock_adapter.dart';
import '../test_helpers/local_storage_fixture.dart';

double _noJitter() => 0.0;

Future<bool> _online() async => false;
Future<bool> _offline() async => true;

void main() {
  late Directory tempDir;

  setUpAll(() async {
    tempDir = await setUpLocalStorage();
  });

  tearDownAll(() async {
    await tearDownLocalStorage(tempDir);
  });

  setUp(() {
    ApiClient.retryPolicy = const RetryPolicy(
      random: _noJitter,
      isOffline: _online,
    );
  });

  tearDown(() async {
    await SecureStorage.clearAuth();
    restoreDioAdapter();
    ApiClient.retryPolicy = const RetryPolicy();
  });

  group('transient failures', () {
    test('a 503 that clears on the second attempt is not shown to the user',
        () async {
      var attempts = 0;

      installMockDioAdapter((options) {
        attempts++;
        if (attempts == 1) return const MockDioResponse(503, {'detail': 'down'});
        return const MockDioResponse(200, {'user': {'name': 'Asha'}});
      });

      ApiClient.init();
      final response = await ApiClient.dio.get('/dashboard');

      expect(attempts, 2);
      expect(response.statusCode, 200);
      expect(response.data['user']['name'], 'Asha');
    });

    test('each retryable status is retried', () async {
      for (final status in [429, 502, 503, 504]) {
        var attempts = 0;

        installMockDioAdapter((options) {
          attempts++;
          if (attempts == 1) return MockDioResponse(status);
          return const MockDioResponse(200, {'ok': true});
        });

        ApiClient.init();
        final response = await ApiClient.dio.get('/dashboard');

        expect(attempts, 2, reason: 'status $status');
        expect(response.statusCode, 200, reason: 'status $status');
      }
    });

    test('a persistent failure gives up after the attempt ceiling', () async {
      var attempts = 0;

      installMockDioAdapter((options) {
        attempts++;
        return const MockDioResponse(503);
      });

      ApiClient.init();

      await expectLater(
        ApiClient.dio.get('/dashboard'),
        throwsA(isA<DioException>()),
      );

      // The original send plus `maxAttempts` replays. A persistently
      // failing endpoint costs a bounded number of requests, not an
      // unbounded one.
      expect(attempts, 1 + ApiClient.retryPolicy.maxAttempts);
    });

    test('a 404 is not retried — it is an answer, not a delay', () async {
      var attempts = 0;

      installMockDioAdapter((options) {
        attempts++;
        return const MockDioResponse(404, {'detail': 'no such thing'});
      });

      ApiClient.init();

      await expectLater(
        ApiClient.dio.get('/cycle/2026-01-01'),
        throwsA(isA<DioException>()),
      );
      expect(attempts, 1);
    });

    test('a POST that fails transiently is not replayed', () async {
      // The duplicate-log case. A `POST /cycle/log` that got a 503 may
      // already have been committed server-side.
      var attempts = 0;

      installMockDioAdapter((options) {
        attempts++;
        return const MockDioResponse(503);
      });

      ApiClient.init();

      await expectLater(
        ApiClient.dio.post('/cycle/log', data: {'start_date': '2026-01-01'}),
        throwsA(isA<DioException>()),
      );
      expect(attempts, 1);
    });

    test('a DELETE that fails transiently is not replayed', () async {
      var attempts = 0;

      installMockDioAdapter((options) {
        attempts++;
        return const MockDioResponse(503);
      });

      ApiClient.init();

      await expectLater(
        ApiClient.dio.delete('/cycle/2026-01-01'),
        throwsA(isA<DioException>()),
      );
      expect(attempts, 1);
    });

    test('a 429 carrying Retry-After is still retried', () async {
      var attempts = 0;

      installMockDioAdapter((options) {
        attempts++;
        if (attempts == 1) {
          return const MockDioResponse(
            429,
            {'detail': 'Too many requests'},
            {'retry-after': ['0']},
          );
        }
        return const MockDioResponse(200, {'ok': true});
      });

      ApiClient.init();
      final response = await ApiClient.dio.get('/dashboard');

      expect(attempts, 2);
      expect(response.statusCode, 200);
    });

    test('a device with no network does not spend its retry budget', () async {
      ApiClient.retryPolicy = const RetryPolicy(
        random: _noJitter,
        isOffline: _offline,
      );

      var attempts = 0;

      installMockDioAdapter((options) {
        attempts++;
        return const MockDioResponse(503);
      });

      ApiClient.init();

      await expectLater(
        ApiClient.dio.get('/dashboard'),
        throwsA(isA<DioException>()),
      );
      expect(attempts, 1);
    });
  });

  group('deadlines', () {
    test('the assistant is given the long budget, everything else is not',
        () async {
      final seen = <String, Duration?>{};

      installMockDioAdapter((options) {
        seen[options.path] = options.receiveTimeout;
        return const MockDioResponse(200, {'response': 'hello'});
      });

      ApiClient.init();
      await ApiClient.dio.post('/assistant/chat', data: {'message': 'hi'});
      await ApiClient.dio.get('/dashboard');

      expect(seen['/assistant/chat'], kLongTimeout);
      expect(seen['/dashboard'], kDefaultTimeout);
    });

    test('the send deadline is set too, not only connect and receive',
        () async {
      Duration? sendTimeout;

      installMockDioAdapter((options) {
        sendTimeout = options.sendTimeout;
        return const MockDioResponse(200, {'ok': true});
      });

      ApiClient.init();
      await ApiClient.dio.get('/dashboard');

      expect(sendTimeout, kDefaultTimeout);
    });
  });

  group('the refresh path stays separate', () {
    test('a 401 refreshes and replays once, without touching the retry budget',
        () async {
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('valid-refresh-token');

      var dashboardCalls = 0;
      var refreshCalls = 0;

      installMockDioAdapter((options) {
        if (options.path == '/auth/refresh') {
          refreshCalls++;
          return const MockDioResponse(200, {
            'access_token': 'fresh-access-token',
            'refresh_token': 'fresh-refresh-token',
          });
        }

        dashboardCalls++;
        if (options.headers['Authorization'] == 'Bearer fresh-access-token') {
          return const MockDioResponse(200, {'ok': true});
        }
        return const MockDioResponse(401, {'detail': 'Token expired'});
      });

      ApiClient.init();
      final response = await ApiClient.dio.get('/dashboard');

      expect(response.statusCode, 200);
      expect(refreshCalls, 1);
      // Once with the stale token, once with the fresh one. Not four.
      expect(dashboardCalls, 2);
    });

    test('a request replayed after a refresh does not then enter the retry loop',
        () async {
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('valid-refresh-token');

      var dashboardCalls = 0;

      installMockDioAdapter((options) {
        if (options.path == '/auth/refresh') {
          return const MockDioResponse(200, {
            'access_token': 'fresh-access-token',
            'refresh_token': 'fresh-refresh-token',
          });
        }

        dashboardCalls++;
        if (options.headers['Authorization'] == 'Bearer fresh-access-token') {
          // The replay lands on a backend that is now failing transiently.
          return const MockDioResponse(503);
        }
        return const MockDioResponse(401, {'detail': 'Token expired'});
      });

      ApiClient.init();

      await expectLater(
        ApiClient.dio.get('/dashboard'),
        throwsA(isA<DioException>()),
      );

      // The stale-token send and the one replay. The two budgets must not
      // multiply into six requests.
      expect(dashboardCalls, 2);
    });

    test('a refresh answering 200 with the wrong body signs the user out',
        () async {
      // The `TypeError` case. `response.data['access_token'] as String`
      // threw for a body like this, and the throw escaped the interceptor:
      // credentials were left in place, the unauthorized callback never
      // fired, and the user sat there signed in with a dead token.
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('valid-refresh-token');

      var unauthorizedCalls = 0;

      installMockDioAdapter((options) {
        if (options.path == '/auth/refresh') {
          return const MockDioResponse(200, {'message': 'service unavailable'});
        }
        return const MockDioResponse(401, {'detail': 'Token expired'});
      });

      ApiClient.init(onUnauthorized: () => unauthorizedCalls++);

      await expectLater(
        ApiClient.dio.get('/dashboard'),
        throwsA(isA<DioException>()),
      );

      expect(unauthorizedCalls, 1);
      expect(await SecureStorage.getToken(), isNull);
      expect(await SecureStorage.getRefreshToken(), isNull);
    });

    test('a refresh that omits a rotated token keeps the one already stored',
        () async {
      // A backend that does not rotate refresh tokens sends only an access
      // token. Overwriting the stored refresh token with nothing would
      // sign the user out at the next refresh.
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('long-lived-refresh-token');

      installMockDioAdapter((options) {
        if (options.path == '/auth/refresh') {
          return const MockDioResponse(200, {
            'access_token': 'fresh-access-token',
          });
        }
        if (options.headers['Authorization'] == 'Bearer fresh-access-token') {
          return const MockDioResponse(200, {'ok': true});
        }
        return const MockDioResponse(401, {'detail': 'Token expired'});
      });

      ApiClient.init();
      final response = await ApiClient.dio.get('/dashboard');

      expect(response.statusCode, 200);
      expect(await SecureStorage.getRefreshToken(), 'long-lived-refresh-token');
    });
  });
}
