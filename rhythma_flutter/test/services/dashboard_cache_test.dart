import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/services/dashboard_cache.dart';

/// Issue #510.
///
/// `saveCachedDashboard` has written a `dashboard_cache_timestamp` on
/// every save since the cache was added, and nothing read it. A cache
/// written six weeks ago rendered exactly like one written thirty seconds
/// ago — and what is cached is `{day, total, nextPeriodDays}`, day counts
/// computed against the date of the request, which are the numbers in this
/// app guaranteed to be wrong tomorrow.
///
/// Everything here is a pure function of `(savedAt, now)`, so none of it
/// depends on the wall clock.
void main() {
  const policy = kDashboardCachePolicy;

  final now = DateTime.utc(2026, 8, 24, 12, 0);

  Map<String, dynamic> payload() => {
        'user': {'name': 'Asha'},
        'cycle': {'day': 12, 'total': 28, 'nextPeriodDays': 16},
        'insights': {'averageCycleLength': 28},
      };

  DashboardCacheEntry evaluateAged(Duration age) => policy.evaluate(
        data: payload(),
        savedAt: now.subtract(age),
        now: now,
      );

  group('the thresholds', () {
    test('a cache from a few minutes ago is fresh', () {
      expect(
        policy.statusForAge(const Duration(minutes: 5)),
        DashboardCacheStatus.fresh,
      );
    });

    test('the freshness window ends at six hours', () {
      expect(
        policy.statusForAge(const Duration(hours: 5, minutes: 59)),
        DashboardCacheStatus.fresh,
      );
      expect(
        policy.statusForAge(const Duration(hours: 6)),
        DashboardCacheStatus.stale,
      );
    });

    test('a cache from yesterday is stale, not expired', () {
      // Stale-and-labelled is the offline-first behaviour. Refusing to
      // show a day-old dashboard on a phone with no signal would be a
      // worse outcome than showing it with its age attached.
      expect(
        policy.statusForAge(const Duration(days: 1)),
        DashboardCacheStatus.stale,
      );
    });

    test('the showable window ends at seven days', () {
      expect(
        policy.statusForAge(const Duration(days: 6, hours: 23)),
        DashboardCacheStatus.stale,
      );
      expect(
        policy.statusForAge(const Duration(days: 7)),
        DashboardCacheStatus.expired,
      );
    });

    test('the three-week-old cache from the issue is expired', () {
      expect(
        policy.statusForAge(const Duration(days: 21)),
        DashboardCacheStatus.expired,
      );
    });

    test('no age at all is absent', () {
      expect(policy.statusForAge(null), DashboardCacheStatus.absent);
    });

    test('a timestamp in the future is treated as fresh, not expired', () {
      // A phone whose clock was wrong when the cache was written, or that
      // has since been corrected backwards. The data is almost certainly
      // recent, and refusing to show a woman her dashboard because her
      // clock is off would be the wrong way to be careful.
      expect(
        policy.statusForAge(const Duration(hours: -3)),
        DashboardCacheStatus.fresh,
      );
    });

    test('the thresholds can be overridden', () {
      const strict = DashboardCachePolicy(
        freshFor: Duration(minutes: 30),
        showStaleFor: Duration(hours: 12),
      );

      expect(
        strict.statusForAge(const Duration(hours: 1)),
        DashboardCacheStatus.stale,
      );
      expect(
        strict.statusForAge(const Duration(days: 1)),
        DashboardCacheStatus.expired,
      );
    });
  });

  group('evaluating a saved payload', () {
    test('a fresh entry carries the data and needs no notice', () {
      final entry = evaluateAged(const Duration(minutes: 20));

      expect(entry.status, DashboardCacheStatus.fresh);
      expect(entry.hasUsableData, isTrue);
      expect(entry.needsAgeNotice, isFalse);
      expect(entry.data!['cycle']['day'], 12);
    });

    test('a stale entry carries the data and its age', () {
      final entry = evaluateAged(const Duration(days: 2));

      expect(entry.status, DashboardCacheStatus.stale);
      expect(entry.hasUsableData, isTrue);
      expect(entry.needsAgeNotice, isTrue);
      expect(entry.age, const Duration(days: 2));
      expect(entry.savedAt, now.subtract(const Duration(days: 2)));
    });

    test('an expired entry carries no data at all', () {
      // The regression, stated directly. A caller that only checks for
      // null cannot accidentally render a three-week-old cycle day as
      // today's.
      final entry = evaluateAged(const Duration(days: 21));

      expect(entry.status, DashboardCacheStatus.expired);
      expect(entry.isExpired, isTrue);
      expect(entry.hasUsableData, isFalse);
      expect(entry.data, isNull);
    });

    test('a payload with no timestamp is expired, not fresh', () {
      // It can only come from a cache written before the timestamp
      // existed. "We do not know how old this is" must not resolve to
      // "show it as today's" — that is the bug, restated.
      final entry = policy.evaluate(data: payload(), savedAt: null, now: now);

      expect(entry.status, DashboardCacheStatus.expired);
      expect(entry.data, isNull);
    });

    test('no payload is absent, whatever the timestamp says', () {
      final entry = policy.evaluate(
        data: null,
        savedAt: now.subtract(const Duration(minutes: 1)),
        now: now,
      );

      expect(entry.status, DashboardCacheStatus.absent);
      expect(entry.hasUsableData, isFalse);
      expect(entry.isExpired, isFalse);
    });

    test('an empty payload is absent rather than a blank dashboard', () {
      final entry = policy.evaluate(data: {}, savedAt: now, now: now);

      expect(entry.status, DashboardCacheStatus.absent);
    });
  });

  group('describing the age', () {
    test('under a minute reads as just now', () {
      expect(
        describeCacheAge(const Duration(seconds: 40)),
        const CacheAgeDescription(CacheAgeUnit.justNow, 0),
      );
    });

    test('minutes up to an hour', () {
      expect(
        describeCacheAge(const Duration(minutes: 37)),
        const CacheAgeDescription(CacheAgeUnit.minutes, 37),
      );
      expect(
        describeCacheAge(const Duration(minutes: 59)),
        const CacheAgeDescription(CacheAgeUnit.minutes, 59),
      );
    });

    test('hours rather than a large number of minutes', () {
      // "2 hours ago" beats "137 minutes ago": the point of the notice is
      // that she can tell at a glance whether the number on screen can be
      // trusted, and a figure she has to convert is worse at that.
      expect(
        describeCacheAge(const Duration(hours: 2, minutes: 17)),
        const CacheAgeDescription(CacheAgeUnit.hours, 2),
      );
    });

    test('days past twenty-four hours', () {
      expect(
        describeCacheAge(const Duration(hours: 23, minutes: 59)),
        const CacheAgeDescription(CacheAgeUnit.hours, 23),
      );
      expect(
        describeCacheAge(const Duration(days: 3, hours: 5)),
        const CacheAgeDescription(CacheAgeUnit.days, 3),
      );
    });

    test('a negative age reads as just now rather than as nonsense', () {
      expect(
        describeCacheAge(const Duration(hours: -2)),
        const CacheAgeDescription(CacheAgeUnit.justNow, 0),
      );
    });
  });
}
