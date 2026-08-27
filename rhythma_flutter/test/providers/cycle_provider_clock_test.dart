import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/providers/cycle_provider.dart';
import 'package:rhythma/services/local_storage_service.dart';
import '../test_helpers/local_storage_fixture.dart';

/// Midnight rollover in [CycleProvider] (issue #539).
///
/// `_today` was a `final` field initialised with `DateTime.now()`, and
/// `main.dart` builds the provider once for the lifetime of the process:
///
///     final DateTime _today = DateTime.now();
///     ...
///     ChangeNotifierProvider(create: (_) => CycleProvider()),
///
/// Nothing refreshed it. A backgrounded app is not killed on any schedule
/// the user controls, so `_today` was "whatever day it was when Rhythma
/// last cold-started".
///
/// `CalendarGrid` called `DateTime.now()` itself, so the grid stayed
/// current while the provider did not. The grid drew today's cell as
/// tappable and not-future; the tap called `selectDate`; `selectDate`
/// compared it against a stale "today" and returned. Nothing happened at
/// all — and it stayed that way until the app was force-quit.
///
/// Every test here drives a fake clock across midnight rather than waiting
/// for one. That seam did not exist before this change, which is why the
/// existing suite could only phrase its future-date case as
/// `DateTime.now().add(const Duration(days: 10))`.
class _FakeClock {
  _FakeClock(this._now);

  DateTime _now;

  DateTime call() => _now;

  void set(DateTime value) => _now = value;

  void advance(Duration by) => _now = _now.add(by);
}

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await LocalStorageService.mergeProfile({'last_period': '2026-01-28'});
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  group('CycleProvider midnight rollover (#539)', () {
    test('the reproduction: a tap on the new today is accepted', () {
      // Opened at 23:50, still open at 00:10.
      final clock = _FakeClock(DateTime(2026, 3, 10, 23, 50));
      final provider = CycleProvider(clock: clock.call);

      clock.set(DateTime(2026, 3, 11, 0, 10));
      provider.selectDate(DateTime(2026, 3, 11));

      // Before this change `selectDate` measured against a `_today` still
      // holding 10 March, decided 11 March was in the future, and returned
      // without selecting anything or saying so.
      expect(provider.selectedDate, DateTime(2026, 3, 11));
    });

    test('selecting the new today notifies listeners', () {
      final clock = _FakeClock(DateTime(2026, 3, 10, 23, 50));
      final provider = CycleProvider(clock: clock.call);
      var notifications = 0;
      provider.addListener(() => notifications++);

      clock.set(DateTime(2026, 3, 11, 0, 10));
      provider.selectDate(DateTime(2026, 3, 11));

      expect(notifications, 1);
    });

    test('today follows the clock instead of the construction time', () {
      final clock = _FakeClock(DateTime(2026, 3, 10, 23, 50));
      final provider = CycleProvider(clock: clock.call);

      expect(provider.today, DateTime(2026, 3, 10));

      clock.advance(const Duration(minutes: 20));

      expect(provider.today, DateTime(2026, 3, 11));
    });

    test('today is normalised to midnight, not the current instant', () {
      final clock = _FakeClock(DateTime(2026, 3, 10, 14, 37, 22));

      expect(CycleProvider(clock: clock.call).today, DateTime(2026, 3, 10));
    });

    test('jumpToToday lands on the new day, not the previous one', () {
      final clock = _FakeClock(DateTime(2026, 3, 31, 23, 55));
      final provider = CycleProvider(clock: clock.call);

      clock.set(DateTime(2026, 4, 1, 0, 5));
      provider.jumpToToday();

      // The "Today" button used to jump to yesterday and highlight it as
      // today — and on the 1st, into the previous month entirely.
      expect(provider.selectedDate, DateTime(2026, 4, 1));
      expect(provider.displayedMonth, DateTime(2026, 4));
    });

    test('rollover across a year boundary', () {
      final clock = _FakeClock(DateTime(2026, 12, 31, 23, 59));
      final provider = CycleProvider(clock: clock.call);

      clock.set(DateTime(2027, 1, 1, 0, 1));

      expect(provider.today, DateTime(2027, 1, 1));
      provider.jumpToToday();
      expect(provider.displayedMonth, DateTime(2027, 1));
    });

    test('a genuinely future date is still refused after rollover', () {
      // The guard is fixed, not removed: no logging for days that have
      // not happened.
      final clock = _FakeClock(DateTime(2026, 3, 10, 23, 50));
      final provider = CycleProvider(clock: clock.call);

      clock.set(DateTime(2026, 3, 11, 0, 10));
      provider.selectDate(DateTime(2026, 3, 12));

      expect(provider.selectedDate, DateTime(2026, 3, 10));
    });
  });

  group('CycleProvider.refreshIfDayChanged (#539)', () {
    test('does nothing within the same day', () {
      final clock = _FakeClock(DateTime(2026, 3, 10, 9, 0));
      final provider = CycleProvider(clock: clock.call);
      var notifications = 0;
      provider.addListener(() => notifications++);

      clock.advance(const Duration(hours: 6));

      expect(provider.refreshIfDayChanged(), isFalse);
      expect(notifications, 0);
    });

    test('notifies once when the day changes, and not again', () {
      final clock = _FakeClock(DateTime(2026, 3, 10, 23, 50));
      final provider = CycleProvider(clock: clock.call);
      var notifications = 0;
      provider.addListener(() => notifications++);

      clock.set(DateTime(2026, 3, 11, 0, 10));

      expect(provider.refreshIfDayChanged(), isTrue);
      expect(provider.refreshIfDayChanged(), isFalse);
      expect(notifications, 1);
    });

    test('moves the selection when it was pinned to the old today', () {
      final clock = _FakeClock(DateTime(2026, 3, 10, 23, 50));
      final provider = CycleProvider(clock: clock.call);

      clock.set(DateTime(2026, 3, 11, 0, 10));
      provider.refreshIfDayChanged();

      expect(provider.selectedDate, DateTime(2026, 3, 11));
    });

    test('leaves a deliberately chosen earlier day alone', () {
      // She picked 5 March to fill in a missed log and left the app open.
      // Coming back to a different day than the one she chose would lose
      // her place.
      final clock = _FakeClock(DateTime(2026, 3, 10, 23, 50));
      final provider = CycleProvider(clock: clock.call);
      provider.selectDate(DateTime(2026, 3, 5));

      clock.set(DateTime(2026, 3, 11, 0, 10));
      provider.refreshIfDayChanged();

      expect(provider.selectedDate, DateTime(2026, 3, 5));
    });

    test('jumpToToday resets the rollover baseline', () {
      final clock = _FakeClock(DateTime(2026, 3, 10, 23, 50));
      final provider = CycleProvider(clock: clock.call);

      clock.set(DateTime(2026, 3, 11, 0, 10));
      provider.jumpToToday();

      // jumpToToday has already moved everything to the new day, so a
      // resume immediately afterwards has nothing to repaint.
      expect(provider.refreshIfDayChanged(), isFalse);
    });
  });

  group('CycleProvider default clock', () {
    test('tracks the real clock when none is injected', () {
      final now = DateTime.now();

      expect(
        CycleProvider().today,
        DateTime(now.year, now.month, now.day),
      );
    });

    test('phase math is unaffected by the injected clock', () {
      // The clock decides what "today" is; it must not touch the cycle-day
      // arithmetic, which is anchored on the profile's last_period.
      final clock = _FakeClock(DateTime(2026, 6, 1, 12, 0));
      final withClock = CycleProvider(clock: clock.call);
      final withoutClock = CycleProvider();

      expect(
        withClock.phaseKey(DateTime(2026, 1, 30)),
        withoutClock.phaseKey(DateTime(2026, 1, 30)),
      );
      expect(withClock.phaseKey(DateTime(2026, 1, 30)), 'menstrual');
    });
  });
}
