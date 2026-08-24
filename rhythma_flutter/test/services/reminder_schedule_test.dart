import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/services/reminder_schedule.dart';

/// Issue #511.
///
/// Both automatic reminders silently stopped scheduling, and the failures
/// were bare `return`s — the Settings toggle stayed on while nothing was
/// registered with the OS. The arithmetic is pure here so every case can
/// be stated as a date rather than reproduced on a device.
void main() {
  // A Tuesday, mid-morning. Nothing about the tests depends on which day
  // it is; fixing it keeps them independent of the wall clock.
  final now = DateTime(2026, 8, 24, 10, 0);

  group('the period reminder', () {
    test('fires two days before the next projected period', () {
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2026, 8, 10),
        cycleLength: 28,
        daysBefore: 2,
        now: now,
      );

      expect(plan.kind, PeriodReminderKind.upcomingPeriod);
      expect(plan.projectedPeriodDate, DateTime(2026, 9, 7));
      expect(plan.at, DateTime(2026, 9, 5));
    });

    test('rolls forward when the first projected cycle has already passed', () {
      // The regression. The old code projected exactly one cycle and
      // returned when that date was behind `now` — so this user, who
      // logged in June and has not opened the app since, got nothing on
      // this launch and nothing on any launch after it.
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2026, 6, 20),
        cycleLength: 28,
        daysBefore: 2,
        now: now,
      );

      expect(plan.kind, PeriodReminderKind.upcomingPeriod);
      expect(plan.at!.isAfter(now), isTrue);
      // 20 Jun + 28 = 18 Jul, + 28 = 15 Aug (past), + 28 = 12 Sep.
      expect(plan.projectedPeriodDate, DateTime(2026, 9, 12));
    });

    test('rolls forward across several cycles, not just one', () {
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2026, 6, 1),
        cycleLength: 30,
        daysBefore: 3,
        now: now,
      );

      expect(plan.kind, PeriodReminderKind.upcomingPeriod);
      expect(plan.at!.isAfter(now), isTrue);
    });

    test('a reminder date that has passed today still rolls to the next cycle', () {
      // The projected period is tomorrow, so the two-days-before reminder
      // was yesterday. Scheduling nothing is what used to happen.
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2026, 7, 29),
        cycleLength: 27,
        daysBefore: 2,
        now: now,
      );

      expect(plan.kind, PeriodReminderKind.upcomingPeriod);
      expect(plan.at!.isAfter(now), isTrue);
    });

    test('an anchor older than the projection horizon asks her to log', () {
      // A year-old anchor is not evidence about this month. Projecting a
      // thirteenth cycle from it would produce a confident-looking date
      // built on nothing — the failure #487 describes on the calendar.
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2025, 8, 1),
        cycleLength: 28,
        daysBefore: 2,
        now: now,
      );

      expect(plan.kind, PeriodReminderKind.logPeriod);
      expect(plan.shouldSchedule, isTrue,
          reason: 'a stale anchor should nudge, not silently schedule nothing');
      expect(plan.at!.isAfter(now), isTrue);
      expect(plan.projectedPeriodDate, isNull);
    });

    test('the horizon is configurable and is measured from the anchor', () {
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2026, 7, 1),
        cycleLength: 28,
        daysBefore: 2,
        now: now,
        maxProjection: const Duration(days: 30),
      );

      expect(plan.kind, PeriodReminderKind.logPeriod);
    });

    test('no anchor at all schedules nothing', () {
      final plan = planPeriodReminder(
        lastPeriod: null,
        cycleLength: 28,
        daysBefore: 2,
        now: now,
      );

      expect(plan.kind, PeriodReminderKind.none);
      expect(plan.shouldSchedule, isFalse);
    });

    test('an anchor in the future asks her to log rather than projecting', () {
      // A wrong clock or a mistyped date. Projecting from it would push
      // the reminder further out, which is the opposite of useful.
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2027, 1, 1),
        cycleLength: 28,
        daysBefore: 2,
        now: now,
      );

      expect(plan.kind, PeriodReminderKind.logPeriod);
      expect(plan.at!.isAfter(now), isTrue);
    });

    test('the nudge is scheduled for tomorrow, not this instant', () {
      // The app is being launched right now; a notification this second
      // would fire over the screen she is already looking at.
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2025, 1, 1),
        cycleLength: 28,
        daysBefore: 2,
        now: now,
      );

      expect(plan.at, DateTime(2026, 8, 25, 10));
    });

    test('a lead time of zero fires on the projected day itself', () {
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2026, 8, 10),
        cycleLength: 28,
        daysBefore: 0,
        now: now,
      );

      expect(plan.at, DateTime(2026, 9, 7));
    });

    test('a negative lead time is treated as zero, not as a date in the past', () {
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2026, 8, 10),
        cycleLength: 28,
        daysBefore: -5,
        now: now,
      );

      expect(plan.at, DateTime(2026, 9, 7));
    });
  });

  group('the declared cycle length', () {
    test('a plausible length is used as given', () {
      expect(normalizeCycleLength(31), 31);
      expect(normalizeCycleLength(15), 15);
      expect(normalizeCycleLength(60), 60);
    });

    test('a missing length falls back to the population default', () {
      expect(normalizeCycleLength(null), kDefaultCycleLength);
    });

    test('an implausible length falls back rather than being trusted', () {
      // Matches the backend's own plausibility band in
      // prediction_service.py. A profile carrying 400 must not produce a
      // reminder in the next century.
      expect(normalizeCycleLength(0), kDefaultCycleLength);
      expect(normalizeCycleLength(3), kDefaultCycleLength);
      expect(normalizeCycleLength(400), kDefaultCycleLength);
      expect(normalizeCycleLength(-28), kDefaultCycleLength);
    });

    test('an implausible length does not stall the projection', () {
      final plan = planPeriodReminder(
        lastPeriod: DateTime(2026, 8, 10),
        cycleLength: 0,
        daysBefore: 2,
        now: now,
      );

      expect(plan.kind, PeriodReminderKind.upcomingPeriod);
      expect(plan.projectedPeriodDate, DateTime(2026, 9, 7));
    });
  });

  group('the daily logging reminder', () {
    test('uses today when the time is still ahead', () {
      expect(
        nextDailyOccurrence(now: now, hour: 19, minute: 0),
        DateTime(2026, 8, 24, 19, 0),
      );
    });

    test('rolls to tomorrow when today\'s time has gone', () {
      // The regression: opening the app at 21:00 used to schedule
      // nothing at all, and evening is when people check a tracker.
      final evening = DateTime(2026, 8, 24, 21, 30);

      expect(
        nextDailyOccurrence(now: evening, hour: 19, minute: 0),
        DateTime(2026, 8, 25, 19, 0),
      );
    });

    test('rolls to tomorrow at the exact minute rather than firing now', () {
      final onTheDot = DateTime(2026, 8, 24, 19, 0);

      expect(
        nextDailyOccurrence(now: onTheDot, hour: 19, minute: 0),
        DateTime(2026, 8, 25, 19, 0),
      );
    });

    test('crosses a month boundary correctly', () {
      final lateOnTheLast = DateTime(2026, 8, 31, 23, 0);

      expect(
        nextDailyOccurrence(now: lateOnTheLast, hour: 19, minute: 0),
        DateTime(2026, 9, 1, 19, 0),
      );
    });

    test('honours a custom time', () {
      expect(
        nextDailyOccurrence(now: now, hour: 8, minute: 30),
        DateTime(2026, 8, 25, 8, 30),
      );
      expect(
        nextDailyOccurrence(now: now, hour: 10, minute: 30),
        DateTime(2026, 8, 24, 10, 30),
      );
    });
  });
}
