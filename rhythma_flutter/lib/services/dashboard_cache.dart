/// How old the saved dashboard is allowed to be, and what to say about it.
///
/// `HomeScreen` painted whatever `LocalStorageService.getCachedDashboard()`
/// returned and then refreshed behind it:
///
/// ```dart
/// void _loadCachedDashboard() {
///   final cached = LocalStorageService.getCachedDashboard();
///   if (cached != null) {
///     setState(() { ...; _loading = false; });
///   }
/// }
/// ```
///
/// `saveCachedDashboard` writes a `dashboard_cache_timestamp` on every
/// save. Nothing read it. There was no getter for it, no expiry anywhere,
/// and a cache written six weeks ago rendered exactly like one written
/// thirty seconds ago (issue #510).
///
/// That matters here more than it would in most apps, because of *what*
/// is cached. The payload is `{user, cycle, insights}`, and `cycle` is
/// `{day, total, nextPeriodDays}` — day counts computed server-side
/// against the date of the request. They are the numbers in this app
/// guaranteed to be wrong tomorrow. A user who last had signal on 3
/// August, opening the app on 24 August, was shown "Cycle Day 12 · next
/// period in 16 days" as a plain statement of fact. She was on day 33 and
/// eleven days late. Being late is the one thing a cycle tracker exists to
/// surface, and the screen said the opposite with no hedge.
///
/// The policy is deliberately three-valued rather than a single "is it
/// expired" boolean, because the two failure modes pull in opposite
/// directions:
///
/// * A blank screen on a phone with no signal is a real cost. The README's
///   premise is that only about a quarter of the intended users have
///   regular mobile internet, so a failed refresh is the *normal* state,
///   not an exceptional one.
/// * Presenting a stale cycle day as today's is worse than showing
///   nothing, because the user cannot tell.
///
/// So: fresh renders silently, stale renders *labelled* with its age, and
/// expired does not render its day counts at all. Stale-and-labelled is
/// the offline-first behaviour; silently-stale was the bug.
///
/// Everything here is a pure function of `(savedAt, now)`. `now` is
/// injectable so the thresholds can be tested without waiting and without
/// the test depending on the wall clock.
library;

/// How the saved dashboard should be treated, given its age.
enum DashboardCacheStatus {
  /// Nothing has been saved for this account yet.
  absent,

  /// Recent enough to show as-is. Roughly "since you last opened the app
  /// today" — a cycle day cannot have changed within this window.
  fresh,

  /// Showable, but only with its age attached. The cycle day may have
  /// advanced by a day or two, which is visible to the user and worth
  /// saying rather than worth hiding.
  stale,

  /// Too old for its day counts to mean anything. The cached numbers are
  /// not shown; the screen asks for a refresh instead.
  expired,
}

/// The saved dashboard, and what may be done with it.
class DashboardCacheEntry {
  const DashboardCacheEntry({
    required this.status,
    this.data,
    this.savedAt,
    this.age,
  });

  const DashboardCacheEntry.absent()
      : status = DashboardCacheStatus.absent,
        data = null,
        savedAt = null,
        age = null;

  final DashboardCacheStatus status;

  /// The cached payload. Null when there is nothing saved, and — on
  /// purpose — also null when the entry has expired: a caller that only
  /// checks for null cannot accidentally render numbers that are too old
  /// to mean anything.
  final Map<String, dynamic>? data;

  final DateTime? savedAt;
  final Duration? age;

  /// True when there is a payload the screen may render.
  bool get hasUsableData => data != null;

  /// True when rendering it obliges the screen to say how old it is.
  bool get needsAgeNotice => status == DashboardCacheStatus.stale;

  /// True when there was something saved but it is too old to show.
  bool get isExpired => status == DashboardCacheStatus.expired;
}

/// The cache policy: two thresholds and the function that applies them.
class DashboardCachePolicy {
  const DashboardCachePolicy({
    this.freshFor = defaultFreshFor,
    this.showStaleFor = defaultShowStaleFor,
  });

  /// Under this age the cache renders with no notice.
  ///
  /// Six hours, not twenty-four: the day counts roll over at midnight, so
  /// a window that can span a midnight can hand the user yesterday's
  /// cycle day with no indication. Six hours can only span one if the app
  /// is opened in the small hours, and that is the case the stale label
  /// exists for.
  static const Duration defaultFreshFor = Duration(hours: 6);

  /// Past this age the cached day counts are not shown at all.
  ///
  /// Seven days is chosen against the thing being cached rather than as a
  /// round number. A cycle day that is a week out is not "slightly off" —
  /// it can put a user in the wrong phase entirely, and for someone who
  /// is late it can hide exactly the fact she opened the app to check.
  static const Duration defaultShowStaleFor = Duration(days: 7);

  final Duration freshFor;
  final Duration showStaleFor;

  /// Classify an age. Exposed separately from [evaluate] so the
  /// thresholds can be tested without constructing a payload.
  DashboardCacheStatus statusForAge(Duration? age) {
    if (age == null) return DashboardCacheStatus.absent;

    // A negative age means the saved timestamp is in the future — a clock
    // that was wrong when the cache was written, or one that has since
    // been corrected backwards. Treated as fresh rather than as expired:
    // the data was almost certainly written recently, and refusing to show
    // a user her dashboard because her phone's clock is off would be a
    // worse outcome than showing it.
    if (age.isNegative) return DashboardCacheStatus.fresh;

    if (age < freshFor) return DashboardCacheStatus.fresh;
    if (age < showStaleFor) return DashboardCacheStatus.stale;
    return DashboardCacheStatus.expired;
  }

  /// Turn a saved payload and its timestamp into a decision.
  ///
  /// A payload with no timestamp is treated as expired, not as fresh. It
  /// can only come from a cache written before the timestamp existed, and
  /// "we do not know how old this is" must not resolve to "show it as
  /// today's" — that is the bug, restated.
  DashboardCacheEntry evaluate({
    required Map<String, dynamic>? data,
    required DateTime? savedAt,
    required DateTime now,
  }) {
    if (data == null || data.isEmpty) {
      return const DashboardCacheEntry.absent();
    }

    if (savedAt == null) {
      return const DashboardCacheEntry(
        status: DashboardCacheStatus.expired,
        data: null,
      );
    }

    final age = now.difference(savedAt);
    final status = statusForAge(age);

    return DashboardCacheEntry(
      status: status,
      data: status == DashboardCacheStatus.expired ? null : data,
      savedAt: savedAt,
      age: age,
    );
  }
}

/// The default policy, so call sites do not each construct one.
const DashboardCachePolicy kDashboardCachePolicy = DashboardCachePolicy();

/// A short, translatable description of how old the saved data is.
///
/// Returns the *pieces* — a unit and a count — rather than a formatted
/// sentence, so the screen can build the sentence in the user's own
/// language instead of this module hard-coding English word order. The
/// app ships in eighteen languages and several of them do not put the
/// number where English does.
class CacheAgeDescription {
  const CacheAgeDescription(this.unit, this.count);

  final CacheAgeUnit unit;
  final int count;

  @override
  bool operator ==(Object other) =>
      other is CacheAgeDescription && other.unit == unit && other.count == count;

  @override
  int get hashCode => Object.hash(unit, count);

  @override
  String toString() => 'CacheAgeDescription($unit, $count)';
}

enum CacheAgeUnit { justNow, minutes, hours, days }

/// Reduce a duration to the coarsest unit that still says something true.
///
/// "2 hours ago" rather than "137 minutes ago": the point of the notice is
/// that the user can tell at a glance whether the number on screen can be
/// trusted, and a precise figure she has to convert is worse at that than
/// a rounded one she does not.
CacheAgeDescription describeCacheAge(Duration age) {
  if (age.isNegative || age.inMinutes < 1) {
    return const CacheAgeDescription(CacheAgeUnit.justNow, 0);
  }
  if (age.inMinutes < 60) {
    return CacheAgeDescription(CacheAgeUnit.minutes, age.inMinutes);
  }
  if (age.inHours < 24) {
    return CacheAgeDescription(CacheAgeUnit.hours, age.inHours);
  }
  return CacheAgeDescription(CacheAgeUnit.days, age.inDays);
}
