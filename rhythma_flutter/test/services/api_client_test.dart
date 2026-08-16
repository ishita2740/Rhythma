import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/services/api_client.dart';
import 'package:rhythma/utils/secure_storage.dart';

import '../test_helpers/dio_mock_adapter.dart';
import '../test_helpers/local_storage_fixture.dart';

void main() {
  late Directory tempDir;

  setUpAll(() async {
    tempDir = await setUpLocalStorage();
  });

  tearDownAll(() async {
    await tearDownLocalStorage(tempDir);
  });

  tearDown(() async {
    await SecureStorage.clearAuth();
    restoreDioAdapter();
  });

  group('ApiClient auto-refresh lifecycle', () {
    test('valid access token makes a successful request', () async {
      await SecureStorage.saveToken('valid-access-token');

      installMockDioAdapter((options) {
        if (options.path == '/dashboard' &&
            options.headers['Authorization'] == 'Bearer valid-access-token') {
          return const MockDioResponse(200, {'user': {'name': 'Asha'}});
        }
        return const MockDioResponse(404);
      });

      ApiClient.init();
      final response = await ApiClient.dio.get('/dashboard');
      expect(response.statusCode, 200);
      expect(response.data['user']['name'], 'Asha');
    });

    test('expired access token triggers refresh and retries original request', () async {
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('valid-refresh-token');

      int refreshCallCount = 0;

      installMockDioAdapter((options) {
        // First call to /dashboard fails with 401
        if (options.path == '/dashboard' &&
            options.headers['Authorization'] == 'Bearer expired-access-token') {
          return const MockDioResponse(401, {'detail': 'Token expired'});
        }

        // Refresh endpoint
        if (options.path == '/auth/refresh') {
          refreshCallCount++;
          final body = options.data as Map<String, dynamic>;
          if (body['refresh_token'] == 'valid-refresh-token') {
            return const MockDioResponse(200, {
              'access_token': 'new-access-token',
              'refresh_token': 'new-refresh-token',
              'token_type': 'bearer',
            });
          }
          return const MockDioResponse(401, {'detail': 'Invalid refresh token'});
        }

        // Retried /dashboard with new token succeeds
        if (options.path == '/dashboard' &&
            options.headers['Authorization'] == 'Bearer new-access-token') {
          return const MockDioResponse(200, {'user': {'name': 'Asha'}});
        }

        return const MockDioResponse(404);
      });

      ApiClient.init();
      final response = await ApiClient.dio.get('/dashboard');

      expect(response.statusCode, 200);
      expect(response.data['user']['name'], 'Asha');
      expect(refreshCallCount, 1);

      // New tokens should be stored
      expect(await SecureStorage.getToken(), 'new-access-token');
      expect(await SecureStorage.getRefreshToken(), 'new-refresh-token');
    });

    test('invalid refresh token forces re-authentication', () async {
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('invalid-refresh-token');

      bool unauthorizedCalled = false;

      installMockDioAdapter((options) {
        if (options.path == '/dashboard') {
          return const MockDioResponse(401, {'detail': 'Token expired'});
        }
        if (options.path == '/auth/refresh') {
          return const MockDioResponse(401, {'detail': 'Invalid refresh token'});
        }
        return const MockDioResponse(404);
      });

      ApiClient.init(onUnauthorized: () {
        unauthorizedCalled = true;
      });

      await expectLater(
        ApiClient.dio.get('/dashboard'),
        throwsA(isA<DioException>()),
      );

      expect(unauthorizedCalled, true);
      expect(await SecureStorage.hasToken(), false);
      expect(await SecureStorage.hasRefreshToken(), false);
    });

    test('concurrent requests share a single refresh operation', () async {
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('valid-refresh-token');

      int refreshCallCount = 0;

      installMockDioAdapter((options) {
        if (options.path == '/dashboard' || options.path == '/profile') {
          if (options.headers['Authorization'] == 'Bearer expired-access-token') {
            return const MockDioResponse(401, {'detail': 'Token expired'});
          }
          if (options.headers['Authorization'] == 'Bearer new-access-token') {
            return MockDioResponse(200, {'path': options.path});
          }
        }
        if (options.path == '/auth/refresh') {
          refreshCallCount++;
          // Simulate a slow refresh to prove concurrency handling
          return const MockDioResponse(200, {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'token_type': 'bearer',
          });
        }
        return const MockDioResponse(404);
      });

      ApiClient.init();

      // Fire two requests simultaneously
      final future1 = ApiClient.dio.get('/dashboard');
      final future2 = ApiClient.dio.get('/profile');

      final results = await Future.wait([future1, future2]);

      expect(results[0].statusCode, 200);
      expect(results[1].statusCode, 200);
      // Only ONE refresh call despite two concurrent 401s
      expect(refreshCallCount, 1);
    });

    test('failed refresh does not cause infinite retry loop', () async {
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('invalid-refresh-token');

      int refreshCallCount = 0;

      installMockDioAdapter((options) {
        if (options.path == '/dashboard') {
          return const MockDioResponse(401, {'detail': 'Token expired'});
        }
        if (options.path == '/auth/refresh') {
          refreshCallCount++;
          return const MockDioResponse(401, {'detail': 'Invalid refresh token'});
        }
        return const MockDioResponse(404);
      });

      ApiClient.init();

      await expectLater(
        ApiClient.dio.get('/dashboard'),
        throwsA(isA<DioException>()),
      );

      // Should only attempt refresh once, not loop forever
      expect(refreshCallCount, 1);
    });

    test('original request preserves method, params, headers, and body when retried', () async {
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('valid-refresh-token');

      Map<String, dynamic>? capturedHeaders;
      String? capturedMethod;
      dynamic capturedData;

      installMockDioAdapter((options) {
        if (options.path == '/cycle/log' &&
            options.headers['Authorization'] == 'Bearer expired-access-token') {
          return const MockDioResponse(401);
        }
        if (options.path == '/auth/refresh') {
          return const MockDioResponse(200, {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'token_type': 'bearer',
          });
        }
        if (options.path == '/cycle/log' &&
            options.headers['Authorization'] == 'Bearer new-access-token') {
          capturedHeaders = Map<String, dynamic>.from(options.headers);
          capturedMethod = options.method;
          capturedData = options.data;
          return const MockDioResponse(201, {'id': 'log-1'});
        }
        return const MockDioResponse(404);
      });

      ApiClient.init();
      final response = await ApiClient.dio.post(
        '/cycle/log',
        data: {'start_date': '2026-05-01', 'flow_intensity': 'light'},
        options: Options(headers: {'X-Custom-Header': 'custom-value'}),
      );

      expect(response.statusCode, 201);
      expect(capturedMethod, 'POST');
      expect(capturedData, {'start_date': '2026-05-01', 'flow_intensity': 'light'});
      expect(capturedHeaders?['X-Custom-Header'], 'custom-value');
      expect(capturedHeaders?['X-Retry-After-Refresh'], '1');
    });

    test('public requests do not trigger token refresh', () async {
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('valid-refresh-token');

      int refreshCallCount = 0;

      installMockDioAdapter((options) {
        if (options.path == '/auth/login') {
          return const MockDioResponse(401, {'detail': 'Invalid credentials'});
        }
        if (options.path == '/auth/refresh') {
          refreshCallCount++;
          return const MockDioResponse(200, {
            'access_token': 'new-token',
            'refresh_token': 'new-refresh',
            'token_type': 'bearer',
          });
        }
        return const MockDioResponse(404);
      });

      ApiClient.init();

      await expectLater(
        ApiClient.dio.post('/auth/login', data: {'email': 'test', 'password': 'wrong'}),
        throwsA(isA<DioException>()),
      );

      // Should NOT have called refresh for a public endpoint
      expect(refreshCallCount, 0);
    });

    test('second 401 after refresh forces logout (no infinite loop)', () async {
      await SecureStorage.saveToken('expired-access-token');
      await SecureStorage.saveRefreshToken('valid-refresh-token');

      int requestCount = 0;

      installMockDioAdapter((options) {
        if (options.path == '/dashboard') {
          requestCount++;
          // Even the retried request gets 401 — simulating a bad state
          return const MockDioResponse(401, {'detail': 'Still unauthorized'});
        }
        if (options.path == '/auth/refresh') {
          return const MockDioResponse(200, {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'token_type': 'bearer',
          });
        }
        return const MockDioResponse(404);
      });

      bool unauthorizedCalled = false;
      ApiClient.init(onUnauthorized: () {
        unauthorizedCalled = true;
      });

      await expectLater(
        ApiClient.dio.get('/dashboard'),
        throwsA(isA<DioException>()),
      );

      // Should have tried once, refreshed, retried once, then given up
      expect(requestCount, 2); // original + 1 retry
      expect(unauthorizedCalled, true);
    });
  });
}
