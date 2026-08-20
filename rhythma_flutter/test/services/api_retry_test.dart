// The retry policy on its own (issue #500).
//
// Every case here is a decision the client makes without an HTTP client in
// the room: which requests may be replayed, which failures are worth
// replaying, how long to wait, and which path gets a longer deadline.
// That is the whole reason the policy is a separate file — the argument
// for each answer is short, and it should be readable without setting up a
// Dio instance and a mock adapter.
//
// `api_client_retry_test.dart` covers the same policy driven through the
// interceptor.

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/services/api_retry.dart';

DioException _statusError(
  int status, {
  String method = 'GET',
  String path = '/dashboard',
  Map<String, dynamic>? headers,
}) {
  final options = RequestOptions(
    path: path,
    method: method,
    headers: headers ?? <String, dynamic>{},
  );
  return DioException(
    requestOptions: options,
    type: DioExceptionType.badResponse,
    response: Response<dynamic>(requestOptions: options, statusCode: status),
  );
}

DioException _transportError(
  DioExceptionType type, {
  String method = 'GET',
}) {
  final options = RequestOptions(path: '/dashboard', method: method);
  return DioException(requestOptions: options, type: type);
}

void main() {
  const policy = RetryPolicy();

  group('which requests may be replayed', () {
    test('the idempotent methods, and only those', () {
      for (final method in ['get', 'GET', 'head', 'options']) {
        expect(policy.isRetryableMethod(method), isTrue, reason: method);
      }
      for (final method in ['post', 'put', 'patch', 'delete']) {
        expect(policy.isRetryableMethod(method), isFalse, reason: method);
      }
    });

    test('a missing method is treated as GET', () {
      expect(policy.isRetryableMethod(null), isTrue);
    });

    test('a POST is never replayed, however transient the failure', () {
      // The constraint the whole file is built around: a POST /cycle/log
      // that timed out may already have been committed, and replaying it
      // would create a second entry for that day.
      for (final status in [429, 502, 503, 504]) {
        expect(
          policy.shouldRetry(_statusError(status, method: 'POST'), 0),
          isFalse,
          reason: '$status',
        );
      }
      expect(
        policy.shouldRetry(
          _transportError(DioExceptionType.receiveTimeout, method: 'POST'),
          0,
        ),
        isFalse,
      );
    });

    test('a DELETE is not replayed even though HTTP calls it idempotent', () {
      // This API answers 404 for a second delete, so a retry after a lost
      // success turns a completed operation into an error the user sees.
      expect(
        policy.shouldRetry(_statusError(503, method: 'DELETE'), 0),
        isFalse,
      );
    });
  });

  group('which failures are worth replaying', () {
    test('the transient statuses', () {
      for (final status in [429, 502, 503, 504]) {
        expect(policy.shouldRetry(_statusError(status), 0), isTrue,
            reason: '$status');
      }
    });

    test('nothing else', () {
      for (final status in [400, 403, 404, 409, 422, 500]) {
        expect(policy.shouldRetry(_statusError(status), 0), isFalse,
            reason: '$status');
      }
    });

    test('401 is left to the refresh path', () {
      // Two budgets that must not compound: a request that spent its
      // transient attempts and then refreshed would be sent six times.
      expect(policy.shouldRetry(_statusError(401), 0), isFalse);
    });

    test('a request with no response at all', () {
      for (final type in [
        DioExceptionType.connectionTimeout,
        DioExceptionType.sendTimeout,
        DioExceptionType.receiveTimeout,
        DioExceptionType.connectionError,
        DioExceptionType.unknown,
      ]) {
        expect(policy.shouldRetry(_transportError(type), 0), isTrue,
            reason: '$type');
      }
    });

    test('a cancellation is not a failure to retry', () {
      // It was aborted by us; replaying it would defeat the abort.
      expect(
        policy.shouldRetry(_transportError(DioExceptionType.cancel), 0),
        isFalse,
      );
    });

    test('a bad certificate is not transient', () {
      expect(
        policy.shouldRetry(_transportError(DioExceptionType.badCertificate), 0),
        isFalse,
      );
    });

    test('the attempt ceiling is checked before anything else', () {
      final error = _statusError(503);
      expect(policy.shouldRetry(error, policy.maxAttempts - 1), isTrue);
      expect(policy.shouldRetry(error, policy.maxAttempts), isFalse);
      expect(policy.shouldRetry(error, policy.maxAttempts + 5), isFalse);
    });

    test('a request already replayed after a refresh does not also retry', () {
      final error = _statusError(
        503,
        headers: {kRetryAfterRefreshHeader: '1'},
      );
      expect(policy.shouldRetry(error, 0), isFalse);
    });
  });

  group('how long to wait', () {
    test('the window grows exponentially', () {
      const full = RetryPolicy(random: _one);

      expect(full.backoffDelay(0).inMilliseconds, 300);
      expect(full.backoffDelay(1).inMilliseconds, 600);
      expect(full.backoffDelay(2).inMilliseconds, 1200);
    });

    test('and is capped', () {
      const full = RetryPolicy(random: _one);

      expect(full.backoffDelay(20), const Duration(seconds: 5));
    });

    test('the jitter spans the whole window, not a fraction of it', () {
      // Without it, every client that failed against the same restart
      // retries at the same instant and the storm is what keeps the
      // backend down.
      const none = RetryPolicy(random: _zero);
      const half = RetryPolicy(random: _half);
      const full = RetryPolicy(random: _one);

      expect(none.backoffDelay(1), Duration.zero);
      expect(half.backoffDelay(1).inMilliseconds, 300);
      expect(full.backoffDelay(1).inMilliseconds, 600);
    });

    test('a real policy stays inside its window', () {
      const real = RetryPolicy();
      for (var i = 0; i < 50; i++) {
        final delay = real.backoffDelay(1);
        expect(delay, greaterThanOrEqualTo(Duration.zero));
        expect(delay, lessThanOrEqualTo(const Duration(milliseconds: 600)));
      }
    });

    test('a server-supplied Retry-After wins over the guess', () {
      const full = RetryPolicy(random: _one);

      expect(
        full.backoffDelay(0, retryAfter: const Duration(seconds: 7)),
        const Duration(seconds: 7),
      );
    });

    test('but an absurd Retry-After is capped', () {
      // A header a proxy got wrong must not park a request for an hour.
      const full = RetryPolicy(random: _one);

      expect(
        full.backoffDelay(0, retryAfter: const Duration(hours: 1)),
        const Duration(seconds: 20),
      );
    });
  });

  group('parsing Retry-After', () {
    test('delta-seconds, which is what this backend sends', () {
      expect(parseRetryAfter('2'), const Duration(seconds: 2));
      expect(parseRetryAfter('  120  '), const Duration(seconds: 120));
      expect(parseRetryAfter('0'), Duration.zero);
    });

    test('an HTTP date, which a proxy in front of it might', () {
      final now = DateTime.utc(2026, 10, 21, 7, 28, 0);

      expect(
        parseRetryAfter('Wed, 21 Oct 2026 07:30:00 GMT', now: now),
        const Duration(minutes: 2),
      );
    });

    test('a date in the past means now, never a negative wait', () {
      final now = DateTime.utc(2026, 10, 21, 7, 28, 0);

      expect(
        parseRetryAfter('Wed, 21 Oct 2026 07:00:00 GMT', now: now),
        Duration.zero,
      );
    });

    test('an ISO-8601 timestamp is accepted too', () {
      final now = DateTime.utc(2026, 10, 21, 7, 28, 0);

      expect(
        parseRetryAfter('2026-10-21T07:29:00Z', now: now),
        const Duration(minutes: 1),
      );
    });

    test('anything unparseable falls back to the computed backoff', () {
      expect(parseRetryAfter(null), isNull);
      expect(parseRetryAfter(''), isNull);
      expect(parseRetryAfter('   '), isNull);
      expect(parseRetryAfter('soon'), isNull);
      expect(parseRetryAfter('-5'), isNull);
      expect(parseRetryAfter('2.5'), isNull);
    });
  });

  group('deadlines', () {
    test('the assistant gets its own budget', () {
      expect(policy.timeoutFor('/assistant/chat'), kLongTimeout);
      expect(
        policy.timeoutFor('https://api.example.com/api/v1/assistant/chat'),
        kLongTimeout,
      );
    });

    test('everything else gets the default', () {
      for (final path in [
        '/dashboard',
        '/cycle/log',
        '/assistant/languages',
        '/auth/login',
      ]) {
        expect(policy.timeoutFor(path), kDefaultTimeout, reason: path);
      }
    });

    test('a missing path gets the default rather than raising', () {
      expect(policy.timeoutFor(null), kDefaultTimeout);
      expect(policy.timeoutFor(''), kDefaultTimeout);
    });
  });

  group('offline suppression', () {
    test('an unconfigured probe never suppresses', () async {
      expect(await const RetryPolicy().shouldSuppressForOffline(), isFalse);
    });

    test('a probe that says offline suppresses the retry', () async {
      const offline = RetryPolicy(isOffline: _alwaysOffline);
      expect(await offline.shouldSuppressForOffline(), isTrue);
    });

    test('a probe that says online does not', () async {
      const online = RetryPolicy(isOffline: _alwaysOnline);
      expect(await online.shouldSuppressForOffline(), isFalse);
    });

    test('a probe that throws means "we do not know", so the retry proceeds',
        () async {
      const broken = RetryPolicy(isOffline: _throws);
      expect(await broken.shouldSuppressForOffline(), isFalse);
    });
  });
}

double _zero() => 0.0;
double _half() => 0.5;
double _one() => 0.999999;

Future<bool> _alwaysOffline() async => true;
Future<bool> _alwaysOnline() async => false;
Future<bool> _throws() async => throw StateError('no connectivity plugin here');
