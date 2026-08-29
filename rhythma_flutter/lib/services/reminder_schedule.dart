/// When the automatic reminders should actually fire.
///
/// `NotificationService` computed both of its schedules inline, and both
/// computations had the same shape of bug: a date that had already passed
/// produced a bare `return`, so nothing was scheduled, the settings toggle
/// stayed on, and nothing anywhere said so (issue #511).
///
/// **The period reminder gave up as soon as `last_period` went stale.**
///
/// ```dart
/// final predictedDate = lastPeriod.add(Duration(days: cycleLength));
/// final reminderDate = predictedDate.subtract(Duration(days: daysBefore));
/// if (reminderDate.isBefore(now)) return;
/// ```
///
/// One anchor, one cycle. Once `now` passed it, `reminderDate` was
/// permanently in the past and this returned without scheduling — on that
/// launch and every launch after it. The anchor only moves when the user
/// logs a period, so the reminder worked for the woman already logging
/// diligently and switched itself off for the woman who had stopped, who
/// is the one the nudge exists to reach.
///
/// **The "daily" logging reminder was a one-shot**, and was skipped
/// outright for anyone who opened the app after 19:00 — which is when
/// people check a tracker.
///
/// Both are pure functions of `(anchor, now)` here, so the arithmetic can
/// be tested without the plugin, without the wall clock, and without a
/// device.
library;

/// What to schedule for the period reminder.
enum PeriodReminderKind {
  /// A normal "your period is expected soon" reminder, at [ReminderPlan.at].
  upcomingPeriod,

  /// The anchor is too old to predict from. Nudge her to log her last
  /// period instead of silently scheduling nothing — which is what used
  /// to happen, and which left a toggle switched on doing nothing.
  logPeriod,

  /// Nothing can be scheduled: no anchor at all, or an unusable one.
  none,
}

/// A scheduling decision.
class ReminderPlan {
  const ReminderPlan(this.kind, this.at, {this.projectedPeriodDate});

  const ReminderPlan.none()
      : kind = PeriodReminderKind.none,
        at = null,
        projectedPeriodDate = null;

  final PeriodReminderKind kind;

  /// When to fire. Null only when [kind] is [PeriodReminderKind.none].
  final DateTime? at;

  /// The period date this reminder is about, for the message. Null for
  /// the "log your period" nudge, which is about not knowing.
  final DateTime? projectedPeriodDate;

  bool get shouldSchedule => kind != PeriodReminderKind.none && at != null;
}

/// How far ahead of an anchor the projection is allowed to run.
///
/// Ninety days is roughly three cycles. Past that the anchor is not
/// evidence about this month in any useful sense — projecting a fourth
/// cycle from a date that old produces a confident-looking prediction
/// built on nothing, which is the failure #487 describes on the calendar.
/// Saying "we've lost track, tell us when your last period was" is both
/// honest and actionable.
const Duration kMaxAnchorProjection = Duration(days: 90);

/// Bounds on a declared cycle length, matching the backend's
/// `prediction_service.MIN_PLAUSIBLE_CYCLE_DAYS` /
/// `MAX_PLAUSIBLE_CYCLE_DAYS`. A profile carrying a nonsense value must
/// not produce a reminder in the year 2400.
const int kMinCycleLength = 15;
const int kMaxCycleLength = 60;
const int kDefaultCycleLength = 28;

/// Clamp a declared cycle length into the plausible range.
int normalizeCycleLength(int? declared) {
  if (declared == null) return kDefaultCycleLength;
  if (declared < kMinCycleLength || declared > kMaxCycleLength) {
    return kDefaultCycleLength;
  }
  return declared;
}

/// Plan the period reminder, rolling the projection forward as needed.
///
/// [lastPeriod] is the anchor from the stored profile, [cycleLength] the
/// declared length, [daysBefore] how far ahead of the projected date to
/// fire, and [now] the moment the app is deciding.
///
/// The projection walks forward one cycle at a time from the anchor until
/// the reminder date is in the future — so a woman who logged in June and
/// has not opened the app since still gets reminded, instead of the
/// reminder switching itself off. It stops at [maxProjection] past the
/// anchor and returns [PeriodReminderKind.logPeriod], because a
/// prediction four cycles out from a stale date is a guess wearing a
/// prediction's clothes.
ReminderPlan planPeriodReminder({
  required DateTime? lastPeriod,
  required int? cycleLength,
  required int daysBefore,
  required DateTime now,
  Duration maxProjection = kMaxAnchorProjection,
}) {
  if (lastPeriod == null) return const ReminderPlan.none();

  final length = normalizeCycleLength(cycleLength);
  final lead = daysBefore < 0 ? 0 : daysBefore;

  // An anchor in the future is a wrong clock or a mistyped date, not a
  // period that has not happened yet. Projecting from it would put the
  // reminder further out still, so it is treated as unusable.
  if (lastPeriod.isAfter(now.add(const Duration(days: 1)))) {
    return ReminderPlan(PeriodReminderKind.logPeriod, _nudgeTime(now));
  }

  final horizon = lastPeriod.add(maxProjection);

  var projected = lastPeriod.add(Duration(days: length));
  while (true) {
    final reminderAt = projected.subtract(Duration(days: lead));

    if (reminderAt.isAfter(now)) {
      // Found a reminder in the future — but only trust it if the period
      // it is about is still inside the horizon.
      if (projected.isAfter(horizon)) {
        return ReminderPlan(
          PeriodReminderKind.logPeriod,
          _nudgeTime(now),
        );
      }
      return ReminderPlan(
        PeriodReminderKind.upcomingPeriod,
        reminderAt,
        projectedPeriodDate: projected,
      );
    }

    if (projected.isAfter(horizon)) {
      // Walked past the horizon without finding a future reminder. The
      // anchor is too old to predict from at all.
      return ReminderPlan(PeriodReminderKind.logPeriod, _nudgeTime(now));
    }

    projected = projected.add(Duration(days: length));
  }
}

/// When to deliver the "we've lost track, log your period" nudge.
///
/// Tomorrow morning rather than immediately: the app is being launched
/// right now, so a notification this second would fire over the screen
/// the user is already looking at.
DateTime _nudgeTime(DateTime now) {
  final tomorrow = DateTime(now.year, now.month, now.day).add(
    const Duration(days: 1),
  );
  return DateTime(tomorrow.year, tomorrow.month, tomorrow.day, 10);
}

/// The next occurrence of [hour]:[minute], today if it is still ahead and
/// tomorrow otherwise.
///
/// The old code built today's time and returned when it had passed, so
/// anyone opening the app after 19:00 got no logging reminder at all —
/// and evening is when people check a tracker. Rolling forward is the
/// whole fix; there is no case in which "that time has gone, so schedule
/// nothing" is what the user asked for by leaving the toggle on.
DateTime nextDailyOccurrence({
  required DateTime now,
  required int hour,
  required int minute,
}) {
  final today = DateTime(now.year, now.month, now.day, hour, minute);
  if (today.isAfter(now)) return today;
  return today.add(const Duration(days: 1));
}
