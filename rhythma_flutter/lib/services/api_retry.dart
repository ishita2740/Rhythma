/// Deciding whether a failed request is worth trying again, and when.
///
/// Issue #500. The web client got this in #408; the mobile client never
/// did. `api_client.dart` set one 10-second deadline for every route and
/// handled exactly one failure:
///
/// ```dart
/// if (statusCode != 401) {
///   // Not an auth error — pass through unchanged.
///   return handler.next(error);
/// }
/// ```
///
/// So on the platform where flaky uplinks are the norm rather than the
/// exception:
///
/// * `POST /assistant/chat` waits on a model call and is routinely cut off
///   at ten seconds, showing an error for an answer the server is about to
///   return — and paying for the model call anyway. The web client gives
///   that one path 45 seconds for exactly this reason.
/// * A 502/503/504 during a deploy is a hard failure. The web client rides
///   through it with three jittered retries.
/// * `Retry-After` is discarded, so a user who hits the assistant's rate
///   limit is told nothing and can hammer the button freely.
/// * `sendTimeout` is unset, so a request whose *body* stalls mid-upload
///   has no deadline at all — which is the failure #408 was opened for.
///
/// This file is the policy, deliberately kept out of the Dio interceptor:
/// the interesting part is a handful of decisions that are worth reading —
/// and worth testing — without an HTTP client in the way. It mirrors
/// `web/src/api/retry.ts` closely enough that the two can be read against
/// each other, because a mobile client and a web client that disagree
/// about when to give up is how the two apps end up showing different
/// errors for the same outage.
library;

import 'dart:math';

import 'package:dio/dio.dart';

/// Default per-request deadline. Matches the web client's `DEFAULT_TIMEOUT_MS`.
const Duration kDefaultTimeout = Duration(seconds: 10);

/// The assistant legitimately runs long — it waits on a model call.
/// Applying the default here would turn a working answer into a timeout,
/// so this endpoint gets its own budget rather than pushing everyone
/// else's up to match.
const Duration kLongTimeout = Duration(seconds: 45);

/// Paths that get [kLongTimeout]. Matched by substring, so it holds whether
/// the caller passes a bare path or a full URL.
const List<String> kLongTimeoutPaths = ['/assistant/chat'];

/// Statuses worth retrying.
///
/// All transient by definition: the server said "not now", not "no". Every
/// other 4xx is a statement about the request itself, and replaying it
/// unchanged would produce the same answer more slowly.
///
/// 401 is deliberately absent. It has its own path — refresh the token and
/// replay once — and the two must not compound: a request that consumed
/// its transient budget and then refreshed would be sent up to six times.
const Set<int> kRetryableStatuses = {429, 502, 503, 504};

/// Methods safe to replay.
///
/// This is the constraint the whole file is built around. A
/// `POST /cycle/log` that timed out may well have been committed
/// server-side — the response was lost, not the write — so replaying it
/// would silently create a second entry for that day. A duplicate log is
/// worse than an error message, because the error is visible and the
/// duplicate quietly corrupts the data every prediction and insight is
/// computed from.
///
/// Only the methods HTTP defines as idempotent are here. `DELETE` is
/// idempotent by spec but omitted deliberately: this API answers 404 for a
/// second delete, so a retry after a lost success turns a completed
/// operation into an error the user sees.
const Set<String> kRetryableMethods = {'get', 'head', 'options'};

/// Header the interceptor stamps on a request it has already replayed
/// after a token refresh. Named here so the retry path can be sure it is
/// not the same counter.
const String kRetryAfterRefreshHeader = 'X-Retry-After-Refresh';

/// Failures where the request never reached a server that answered.
const Set<DioExceptionType> _transportFailures = {
  DioExceptionType.connectionTimeout,
  DioExceptionType.sendTimeout,
  DioExceptionType.receiveTimeout,
  DioExceptionType.connectionError,
  DioExceptionType.unknown,
};

/// How long to wait before an attempt, and whether to make it at all.
///
/// A class rather than free functions so a test can substitute a
/// deterministic [random] and a stubbed [isOffline] without reaching into
/// module state or waiting out real backoff. The default instance is
/// `const`, so the production path allocates nothing.
class RetryPolicy {
  const RetryPolicy({
    this.maxAttempts = 3,
    this.baseBackoff = const Duration(milliseconds: 300),
    this.maxBackoff = const Duration(seconds: 5),
    this.defaultTimeout = kDefaultTimeout,
    this.longTimeout = kLongTimeout,
    this.random,
    this.isOffline,
  });

  /// How many times one request may be replayed by us. Checked before
  /// anything else, so a persistently failing endpoint costs a bounded
  /// number of requests rather than a bounded number *per reason*.
  final int maxAttempts;

  /// First step of the exponential backoff.
  final Duration baseBackoff;

  /// Ceiling on the computed backoff, before jitter.
  final Duration maxBackoff;

  final Duration defaultTimeout;
  final Duration longTimeout;

  /// Source of jitter, in `[0, 1)`. Injectable so a test can pin it.
  final double Function()? random;

  /// Whether the device is known to have no network. Returning `true`
  /// suppresses the retry: there is no point spending the budget on
  /// requests that cannot succeed.
  ///
  /// Injectable, and optional. When it is absent the answer is "we do not
  /// know", and the retry goes ahead — the same direction the web client
  /// takes with `navigator.onLine`, which *"means 'has an interface', not
  /// 'has internet', so it is only trusted in the negative direction"*.
  final Future<bool> Function()? isOffline;

  /// True when this request may be replayed at all.
  bool isRetryableMethod(String? method) =>
      kRetryableMethods.contains((method ?? 'get').toLowerCase());

  /// True when the request never got a response.
  ///
  /// A timeout Dio raised itself, a DNS failure, a refused connection, a
  /// dropped socket. Two exclusions are deliberate:
  /// [DioExceptionType.cancel], because an aborted request was aborted by
  /// us and replaying it defeats the abort; and
  /// [DioExceptionType.badCertificate], because a certificate that failed
  /// validation will fail it again, and retrying a TLS failure is how a
  /// security signal turns into a transient-looking one.
  bool isNetworkError(DioException error) {
    if (error.response != null) return false;
    return _transportFailures.contains(error.type);
  }

  /// Whether to try this request again.
  ///
  /// Order matters. The attempt ceiling comes first so the cost is bounded
  /// regardless of how the request is failing; the method check comes next
  /// because it is the one answer that can never change on a retry.
  bool shouldRetry(DioException error, int attempt) {
    if (attempt >= maxAttempts) return false;
    if (!isRetryableMethod(error.requestOptions.method)) return false;

    // A request already replayed after a token refresh is on the auth
    // path, and its budget is that one replay. Letting it also enter this
    // one would multiply the two.
    if (error.requestOptions.headers[kRetryAfterRefreshHeader] == '1') {
      return false;
    }

    final status = error.response?.statusCode;
    if (status == null) return isNetworkError(error);
    return kRetryableStatuses.contains(status);
  }

  /// How long to wait before attempt `attempt + 1`.
  ///
  /// Exponential with full jitter. The jitter is not decoration: without
  /// it, every client that failed against the same backend restart retries
  /// at the same instant, and the retry storm is what keeps it down.
  /// Randomising across the whole window spreads the load rather than
  /// merely shifting it.
  ///
  /// A server-supplied `Retry-After` always wins. It knows when it will be
  /// ready and we are guessing — capped, because a header a proxy got
  /// wrong should not park a request for an hour.
  Duration backoffDelay(int attempt, {Duration? retryAfter}) {
    if (retryAfter != null) {
      final cap = maxBackoff * 4;
      return retryAfter > cap ? cap : retryAfter;
    }

    final exponential = baseBackoff * pow(2, attempt).toDouble();
    final ceiling = exponential > maxBackoff ? maxBackoff : exponential;
    final jitter = (random ?? Random().nextDouble)();

    return Duration(
      milliseconds: (ceiling.inMilliseconds * jitter).round(),
    );
  }

  /// The deadline for a given request path.
  Duration timeoutFor(String? path) {
    if (path == null || path.isEmpty) return defaultTimeout;
    final matches = kLongTimeoutPaths.any(path.contains);
    return matches ? longTimeout : defaultTimeout;
  }

  /// Whether to skip the retry because the device has no network.
  Future<bool> shouldSuppressForOffline() async {
    final check = isOffline;
    if (check == null) return false;
    try {
      return await check();
    } catch (_) {
      // A connectivity probe that fails tells us nothing, and "we do not
      // know" must not become "do not retry".
      return false;
    }
  }
}

/// Parse `Retry-After`, which comes in two shapes.
///
/// Delta-seconds (`Retry-After: 2`) or an HTTP date
/// (`Retry-After: Wed, 21 Oct 2026 07:28:00 GMT`). The backend emits the
/// delta form — `core/rate_limits.py` puts the real wait there — but a
/// proxy or CDN in front of it can emit either, so both are handled.
///
/// Returns `null` for anything unparseable, so a malformed header falls
/// back to the computed backoff instead of failing the request.
Duration? parseRetryAfter(String? value, {DateTime? now}) {
  if (value == null) return null;

  final trimmed = value.trim();
  if (trimmed.isEmpty) return null;

  // Delta-seconds.
  if (RegExp(r'^\d+$').hasMatch(trimmed)) {
    return Duration(seconds: int.parse(trimmed));
  }

  final at = _parseHttpDate(trimmed);
  if (at == null) return null;

  // A date in the past means "now"; a negative delay would be a bug.
  final delta = at.difference((now ?? DateTime.now()).toUtc());
  return delta.isNegative ? Duration.zero : delta;
}

/// The `Retry-After` header's first entry, whatever case it arrived in.
String? retryAfterHeaderOf(Response<dynamic>? response) {
  final values = response?.headers.map['retry-after'];
  if (values == null || values.isEmpty) return null;
  return values.first;
}

/// RFC 7231's preferred date format, plus the ISO-8601 a misconfigured
/// proxy sometimes sends instead.
///
/// `HttpDate.parse` from `dart:io` would do the first, but pulling
/// `dart:io` into this file would make it unusable on Flutter web, which
/// the app already builds for.
DateTime? _parseHttpDate(String value) {
  final match = RegExp(
    r'^[A-Za-z]{3},\s+(\d{2})\s+([A-Za-z]{3})\s+(\d{4})\s+'
    r'(\d{2}):(\d{2}):(\d{2})\s+GMT$',
  ).firstMatch(value);

  if (match != null) {
    final month = _months[match.group(2)!];
    if (month == null) return null;
    return DateTime.utc(
      int.parse(match.group(3)!),
      month,
      int.parse(match.group(1)!),
      int.parse(match.group(4)!),
      int.parse(match.group(5)!),
      int.parse(match.group(6)!),
    );
  }

  return DateTime.tryParse(value)?.toUtc();
}

const Map<String, int> _months = {
  'Jan': 1,
  'Feb': 2,
  'Mar': 3,
  'Apr': 4,
  'May': 5,
  'Jun': 6,
  'Jul': 7,
  'Aug': 8,
  'Sep': 9,
  'Oct': 10,
  'Nov': 11,
  'Dec': 12,
};
