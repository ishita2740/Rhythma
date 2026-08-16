import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/config/theme.dart';
import 'package:rhythma/l10n/app_localizations_en.dart';
import 'package:rhythma/providers/cycle_provider.dart';
import 'package:rhythma/services/local_storage_service.dart';
import '../test_helpers/local_storage_fixture.dart';

/// Issue #487.
///
/// `CycleProvider` computed the day of cycle with a modulo:
///
/// ```dart
/// final cycleDay = ((daysSince % cycleLength) + cycleLength) % cycleLength;
/// return cycleDay + 1;
/// ```
///
/// off `profile['last_period']` — a single onboarding answer — and nothing
/// else. So the phase repeated forever with period `cycleLength` and never
/// stopped being confident: a user who onboarded in January, logged
/// nothing, and opened the app in August was shown a fully coloured
/// calendar, seven cycles synthesised from one date.
///
/// The file this replaces contained a single test asserting
/// `expect(provider, isNotNull)`, which passed against the broken
/// implementation and against every other one.
void main() {
  late Directory tempDir;
  final l10n = AppLocalizationsEn();

  setUp(() async {
    tempDir = await setUpLocalStorage();
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  /// A run of consecutive bleeding days starting at [start].
  Future<void> logPeriod(DateTime start, {int days = 5}) async {
    for (var offset = 0; offset < days; offset++) {
      final day = start.add(Duration(days: offset));
      await LocalStorageService.saveCycleLog({
        'start_date':
            '${day.year.toString().padLeft(4, '0')}-${day.month.toString().padLeft(2, '0')}-${day.day.toString().padLeft(2, '0')}',
        'flow_intensity': 'medium',
      });
    }
  }

  group('the cycle day no longer wraps', () {
    test('a stale anchor gives up instead of synthesising seven cycles', () async {
      await LocalStorageService.mergeProfile({'last_period': '2026-01-28'});
      final provider = CycleProvider();

      // 200 days after the only date this user ever gave us. The modulo
      // reported day 5 of cycle 8 — "menstrual", in rose, indistinguishable
      // from a period logged last week.
      final august = DateTime(2026, 8, 16);

      expect(provider.cycleDayFor(august), 201);
      expect(provider.phaseOf(august), CyclePhase.overdue);
      expect(provider.phaseKey(august), 'late');
    });

    test('the day count keeps rising rather than resetting at cycleLength',
        () async {
      await LocalStorageService.mergeProfile({'last_period': '2026-01-28'});
      final provider = CycleProvider();

      expect(provider.cycleDayFor(DateTime(2026, 2, 24)), 28);
      // Day 29 was day 1 again under the modulo — the single most
      // misleading number this provider could produce.
      expect(provider.cycleDayFor(DateTime(2026, 2, 25)), 29);
      expect(provider.phaseOf(DateTime(2026, 2, 25)), CyclePhase.overdue);
    });

    test('a date before the anchor is unknown, not folded forward', () async {
      // The modulo was written to "stay positive even if date falls before
      // last_period", which turned "we have no idea" into a confident
      // phase somewhere in the middle of a cycle that had not started.
      await LocalStorageService.mergeProfile({'last_period': '2026-01-28'});
      final provider = CycleProvider();

      expect(provider.cycleDayFor(DateTime(2026, 1, 1)), isNull);
      expect(provider.phaseOf(DateTime(2026, 1, 1)), CyclePhase.unknown);
    });
  });

  group('logged periods are used, not just the onboarding answer', () {
    test('a logged period overrides a months-old onboarding date', () async {
      await LocalStorageService.mergeProfile({'last_period': '2026-01-28'});
      await logPeriod(DateTime(2026, 8, 10));
      final provider = CycleProvider();

      final august = DateTime(2026, 8, 16);
      // Day 7 of the cycle that actually started on the 10th — not day 201
      // from January, and not a wrapped phantom.
      expect(provider.anchorFor(august), DateTime(2026, 8, 10));
      expect(provider.cycleDayFor(august), 7);
      expect(provider.phaseOf(august), CyclePhase.follicular);
    });

    test('the anchor is the latest period on or before the date asked about',
        () async {
      // The calendar renders past months, so a February day must be
      // measured from the period that had started by February.
      await logPeriod(DateTime(2026, 2, 1));
      await logPeriod(DateTime(2026, 3, 1));
      await logPeriod(DateTime(2026, 4, 1));
      final provider = CycleProvider();

      expect(provider.anchorFor(DateTime(2026, 2, 10)), DateTime(2026, 2, 1));
      expect(provider.anchorFor(DateTime(2026, 3, 10)), DateTime(2026, 3, 1));
      expect(provider.anchorFor(DateTime(2026, 4, 10)), DateTime(2026, 4, 1));
    });

    test('a run of bleeding days is one period start, not five', () async {
      await logPeriod(DateTime(2026, 5, 1), days: 5);
      final provider = CycleProvider();

      expect(provider.loggedPeriodStarts(), [DateTime(2026, 5, 1)]);
    });

    test('one missed day does not split a period in two', () async {
      for (final day in [1, 2, 4]) {
        await LocalStorageService.saveCycleLog({
          'start_date': '2026-05-0$day',
          'flow_intensity': 'light',
        });
      }
      final provider = CycleProvider();

      expect(provider.loggedPeriodStarts(), [DateTime(2026, 5, 1)]);
    });

    test('mid-cycle spotting does not open a phantom cycle', () async {
      // Without the minimum-gap rule this produces a 10-day "cycle" that
      // then gets phase boundaries computed against a 28-day length.
      await logPeriod(DateTime(2026, 5, 1));
      await LocalStorageService.saveCycleLog({
        'start_date': '2026-05-11',
        'flow_intensity': 'spotting',
      });
      await logPeriod(DateTime(2026, 5, 29));
      final provider = CycleProvider();

      expect(
        provider.loggedPeriodStarts(),
        [DateTime(2026, 5, 1), DateTime(2026, 5, 29)],
      );
    });

    test('flow logged as none is not a period', () async {
      // `none` is an answer she gave, not an absence of one. Treating it
      // as bleeding would invent a cycle out of "I checked, nothing".
      await LocalStorageService.saveCycleLog({
        'start_date': '2026-05-01',
        'flow_intensity': 'none',
      });
      final provider = CycleProvider();

      expect(provider.loggedPeriodStarts(), isEmpty);
    });

    test('a log with no flow at all is not a period', () async {
      await LocalStorageService.saveCycleLog({
        'start_date': '2026-05-01',
        'mood': 'happy',
      });
      final provider = CycleProvider();

      expect(provider.loggedPeriodStarts(), isEmpty);
    });

    test('legacy capitalised flow values still count as bleeding', () async {
      // Older logs were written with the displayed label rather than the
      // canonical key.
      await LocalStorageService.saveCycleLog({
        'start_date': '2026-05-01',
        'flow_intensity': 'Medium',
      });
      final provider = CycleProvider();

      expect(provider.loggedPeriodStarts(), [DateTime(2026, 5, 1)]);
    });
  });

  group('no anchor at all', () {
    test('is unknown rather than the day of the month', () async {
      // The old fallback was `return date.day` — the calendar day of the
      // month used as a cycle day, which is the exact confusion #92 was
      // filed about. It survived here as the no-anchor path.
      final provider = CycleProvider();

      expect(provider.cycleDayFor(DateTime(2026, 3, 7)), isNull);
      expect(provider.phaseOf(DateTime(2026, 3, 7)), CyclePhase.unknown);
      expect(provider.phase(DateTime(2026, 3, 7), l10n), l10n.cyclePhaseUnknown);
    });

    test('is a muted colour, not a confident phase colour', () async {
      final provider = CycleProvider();

      expect(provider.phaseColor(DateTime(2026, 3, 7)), RhythmaColors.mutedFg);
      expect(provider.phaseColor(DateTime(2026, 3, 20)), RhythmaColors.mutedFg);
    });

    test('an unparseable last_period is treated as no anchor', () async {
      await LocalStorageService.mergeProfile({'last_period': 'not a date'});
      final provider = CycleProvider();

      expect(provider.phaseOf(DateTime(2026, 3, 7)), CyclePhase.unknown);
    });
  });

  group('late and unknown are visually distinct from a known phase', () {
    test('late is muted rather than the luteal colour', () async {
      await LocalStorageService.mergeProfile({'last_period': '2026-01-28'});
      final provider = CycleProvider();

      final late = DateTime(2026, 8, 16);
      expect(provider.phaseColor(late), RhythmaColors.mutedFg);
      expect(provider.phaseColor(late), isNot(RhythmaColors.coral));
      expect(provider.phase(late, l10n), l10n.cyclePhaseLate);
      expect(provider.phase(late, l10n), isNot(l10n.cyclePhaseLuteal));
    });
  });

  group('the three phase methods agree', () {
    test('key, label and colour all come from one computation', () async {
      // They used to recompute the same three boundaries independently —
      // three copies of one ladder, which is how the old day-5/13/16
      // version survived in three places and had to be fixed three times.
      await LocalStorageService.mergeProfile({'last_period': '2026-01-28'});
      final provider = CycleProvider();

      const expectations = {
        'menstrual': [CyclePhase.period],
        'follicular': [CyclePhase.follicular],
        'ovulation': [CyclePhase.ovulation],
        'luteal': [CyclePhase.luteal],
        'late': [CyclePhase.overdue],
      };

      for (var offset = 0; offset < 60; offset++) {
        final date = DateTime(2026, 1, 28).add(Duration(days: offset));
        final phase = provider.phaseOf(date);
        final key = provider.phaseKey(date);

        expect(
          expectations[key]?.contains(phase),
          isTrue,
          reason: 'phaseKey said $key but phaseOf said $phase on $date',
        );
      }
    });

    test('boundaries still scale with the profile cycle length', () async {
      // #316's fix must not regress: the boundaries are derived from
      // `cycle_length`, not from a fixed 5/13/16 ladder.
      await LocalStorageService.mergeProfile({
        'last_period': '2026-01-01',
        'cycle_length': 40,
        'period_duration': 5,
      });
      final provider = CycleProvider();

      // follicularEnd = 20 - 2 = 18, ovulationEnd = 20 + 1 = 21.
      expect(provider.phaseOf(DateTime(2026, 1, 3)), CyclePhase.period);
      expect(provider.phaseOf(DateTime(2026, 1, 15)), CyclePhase.follicular);
      expect(provider.phaseOf(DateTime(2026, 1, 20)), CyclePhase.ovulation);
      expect(provider.phaseOf(DateTime(2026, 1, 30)), CyclePhase.luteal);
      // Day 41 — past the declared 40-day length.
      expect(provider.phaseOf(DateTime(2026, 2, 10)), CyclePhase.overdue);
    });

    test('a zero or negative cycle length is unknown, not a crash', () async {
      await LocalStorageService.mergeProfile({
        'last_period': '2026-01-01',
        'cycle_length': 0,
      });
      final provider = CycleProvider();

      expect(provider.phaseOf(DateTime(2026, 1, 10)), CyclePhase.unknown);
    });
  });
}
