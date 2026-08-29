import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/config/theme.dart';
import 'package:rhythma/l10n/app_localizations_en.dart';
import 'package:rhythma/providers/cycle_provider.dart';
import 'package:rhythma/services/local_storage_service.dart';
import '../test_helpers/local_storage_fixture.dart';

void main() {
  late Directory tempDir;
  final l10n = AppLocalizationsEn();

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await LocalStorageService.mergeProfile({'last_period': '2026-01-28'});
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  group('CycleProvider.phase Calculation Regression Tests (#130)', () {
    test('phase() calculates cycle phase from period start date across month boundaries', () async {
      final provider = CycleProvider();

      // Day 3 of cycle (Jan 30 - Menstrual Phase)
      final day3 = DateTime(2026, 1, 30);
      expect(provider.phase(day3, l10n), equals('Period'));

      // Month boundary: Day 10 of cycle (Feb 6 - Follicular Phase)
      final day10 = DateTime(2026, 2, 6);
      expect(provider.phase(day10, l10n), equals('Follicular'));

      // Day 15 of cycle (Feb 11 - Ovulatory Phase)
      final day15 = DateTime(2026, 2, 11);
      expect(provider.phase(day15, l10n), equals('Ovulation'));

      // Day 22 of cycle (Feb 18 - Luteal Phase)
      final day22 = DateTime(2026, 2, 18);
      expect(provider.phase(day22, l10n), equals('Luteal'));
    });
  });

  group('CycleProvider state management', () {
    test('selectDate stores the normalized date', () {
      final provider = CycleProvider();
      provider.selectDate(DateTime(2026, 3, 10, 14, 30));
      expect(provider.selectedDate, DateTime(2026, 3, 10));
    });

    test('selectDate ignores dates in the future', () {
      final provider = CycleProvider();
      final before = provider.selectedDate;
      provider.selectDate(DateTime.now().add(const Duration(days: 10)));
      expect(provider.selectedDate, before);
    });

    test('setDisplayedMonth changes the month and notifies listeners', () {
      final provider = CycleProvider();
      var notifications = 0;
      provider.addListener(() => notifications++);
      provider.setDisplayedMonth(DateTime(2026, 4, 15));
      expect(provider.displayedMonth, DateTime(2026, 4));
      expect(notifications, 1);
    });

    test('setDisplayedMonth does not notify for the same month', () {
      final provider = CycleProvider();
      final current = provider.displayedMonth;
      provider.setDisplayedMonth(current);
      expect(provider.displayedMonth, current);
    });

    test('jumpToToday resets the displayed month to the current month', () {
      final provider = CycleProvider();
      provider.setDisplayedMonth(DateTime(2025, 1));
      provider.jumpToToday();
      final now = DateTime.now();
      expect(provider.displayedMonth.year, now.year);
      expect(provider.displayedMonth.month, now.month);
    });

    test('hasLogsForDate reflects saved cycle logs', () async {
      final provider = CycleProvider();
      expect(provider.hasLogsForDate(DateTime(2026, 3, 5)), isFalse);
      await LocalStorageService.saveCycleLog({
        'start_date': '2026-03-05',
        'flow_intensity': 'Medium',
      });
      expect(provider.hasLogsForDate(DateTime(2026, 3, 5)), isTrue);
    });
  });

  group('CycleProvider phase color', () {
    test('phaseColor returns the phase color for each day range', () {
      final provider = CycleProvider();
      // last_period is seeded as 2026-01-28 in setUp.
      // Defaults: periodDuration=5, cycleLength=28
      //   follicularEnd = (28/2).floor() - 2 = 12
      //   ovulationEnd  = (28/2).floor() + 1 = 15
      expect(provider.phaseColor(DateTime(2026, 1, 28)), RhythmaColors.rose);     // day 1  → period
      expect(
          provider.phaseColor(DateTime(2026, 2, 6)), RhythmaColors.primary);      // day 10 → follicular
      expect(
          provider.phaseColor(DateTime(2026, 2, 10)), RhythmaColors.teal);        // day 14 → ovulation
      expect(
          provider.phaseColor(DateTime(2026, 2, 18)), RhythmaColors.coral);       // day 22 → luteal
    });

    test('phase is unknown when there is no period to count from', () async {
      // This used to fall back to `return date.day` — the calendar day of
      // the month used as a day of cycle — so the 7th of any month was
      // "Follicular" and the 20th "Luteal" for a user who had never logged
      // or declared anything. That is the same confusion issue #92 was
      // filed about; it was fixed for the anchored path and survived here
      // as the no-anchor fallback.
      //
      // There is no cycle day without a period to count from, and saying
      // so is the honest answer (#487).
      await Hive.box<Map>('user_profile').delete('profile');
      final provider = CycleProvider();

      expect(provider.phase(DateTime(2026, 3, 7), l10n), l10n.cyclePhaseUnknown);
      expect(provider.phase(DateTime(2026, 3, 20), l10n), l10n.cyclePhaseUnknown);
      expect(provider.cycleDayFor(DateTime(2026, 3, 7)), isNull);
    });
  });
}
