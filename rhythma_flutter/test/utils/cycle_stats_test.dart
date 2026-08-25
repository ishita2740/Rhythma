import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/utils/cycle_stats.dart';

/// Issue #522.
///
/// The Insights screen squared the deviations from the mean, averaged
/// them, and never took the square root — then printed the result with the
/// word "days" beside it and used it as a threshold in days. The numbers
/// below are the ones from the issue, so a regression here reads as the
/// symptom a user would see.
void main() {
  group('cycleSpread', () {
    test('reports a two-day spread as two days, not four', () {
      // The headline case. 26 and 30 average 28; each is two days away.
      // The variance is (4 + 4) / 2 = 4, which is what used to be shown.
      final spread = cycleSpread([26, 30]);

      expect(spread, isNotNull);
      expect(spread!.spreadDays, 2.0);
      expect(spread.meanDays, 28.0);
      expect(spread.sampleSize, 2);
    });

    test('reports a five-day spread as five days, not twenty-five', () {
      // Where the quadratic error stops being subtle: this user was told
      // her cycle varies by twenty-five days.
      final spread = cycleSpread([23, 33]);

      expect(spread!.spreadDays, 5.0);
      expect(spread.meanDays, 28.0);
    });

    test('is unchanged at a one-day spread, where the bug was invisible', () {
      // 1 squared is 1, which is why nobody noticed.
      expect(cycleSpread([27, 29])!.spreadDays, 1.0);
    });

    test('averages the distances rather than squaring them', () {
      // 25, 28, 31 average 28; distances 3, 0, 3; mean absolute deviation
      // 2. The variance is 6.
      expect(cycleSpread([25, 28, 31])!.spreadDays, 2.0);
    });

    test('is zero for cycles that are all the same length', () {
      // A real answer, not a missing one.
      final spread = cycleSpread([28, 28, 28]);
      expect(spread!.spreadDays, 0.0);
      expect(spread.sampleSize, 3);
    });

    test('is null below two usable cycles', () {
      // Not zero. Zero reads as "perfectly regular" and used to be fed
      // straight into the stability verdict.
      expect(cycleSpread([]), isNull);
      expect(cycleSpread([28]), isNull);
    });

    test('drops non-positive lengths rather than letting them skew the mean',
        () {
      expect(cycleSpread([28, 0, 28]), equals(cycleSpread([28, 28])));
      expect(cycleSpread([28, -5, 28])!.sampleSize, 2);
    });

    test('returns null when filtering leaves fewer than two', () {
      expect(cycleSpread([28, 0]), isNull);
    });

    test('does not depend on the order of the lengths', () {
      expect(cycleSpread([26, 30, 28]), equals(cycleSpread([30, 28, 26])));
    });

    test('rounds to one decimal place', () {
      // 27, 28, 30: mean 28.333…, distances 1.333…, 0.333…, 1.666…,
      // mean absolute deviation 1.111…
      final spread = cycleSpread([27, 28, 30]);
      expect(spread!.spreadDays, 1.1);
      expect(spread.meanDays, 28.3);
    });
  });

  group('labels', () {
    test('a whole number of days loses its trailing zero', () {
      // Otherwise the tile reads "±2.0 days" next to another user's
      // "±2.5 days".
      expect(cycleSpread([26, 30])!.spreadLabel, '2');
      expect(cycleSpread([26, 30])!.meanLabel, '28');
    });

    test('a fractional spread keeps its decimal', () {
      expect(cycleSpread([27, 28, 30])!.spreadLabel, '1.1');
    });

    test('zero is labelled as zero', () {
      expect(cycleSpread([28, 28])!.spreadLabel, '0');
    });
  });

  group('meanOf', () {
    test('averages the usable values', () {
      expect(meanOf([26, 30]), 28.0);
    });

    test('ignores non-positive values', () {
      expect(meanOf([26, 0, 30]), 28.0);
    });

    test('is null with nothing usable', () {
      expect(meanOf([]), isNull);
      expect(meanOf([0, -1]), isNull);
    });
  });

  group('isSteadyCycle', () {
    test('a two-day spread is steady', () {
      // This is the verdict the bug got wrong: 26 and 30 scored 4 against
      // a threshold of 3, so a woman with regular cycles was shown
      // "Moderate" in a warning colour.
      expect(isSteadyCycle(cycleSpread([26, 30])), isTrue);
    });

    test('a five-day spread is not', () {
      expect(isSteadyCycle(cycleSpread([23, 33])), isFalse);
    });

    test('the threshold is inclusive', () {
      // 25 and 31 average 28, three days either side.
      expect(cycleSpread([25, 31])!.spreadDays, kSteadyCycleSpreadDays);
      expect(isSteadyCycle(cycleSpread([25, 31])), isTrue);
    });

    test('is null when there is nothing to judge', () {
      // Not false, and not true. A user who has logged one cycle used to
      // be told her cycles were healthy and stabilising.
      expect(isSteadyCycle(null), isNull);
      expect(isSteadyCycle(cycleSpread([28])), isNull);
    });
  });

  group('agreement with the web app', () {
    // `web/src/lib/cycleStats.ts` computes the same statistic for the same
    // tile. These are the fixtures from its own test file; the two
    // platforms reporting different numbers for one account is the reason
    // this module is a port rather than a fresh implementation.
    test('matches the documented web examples', () {
      expect(cycleSpread([26, 30])!.spreadDays, 2.0);
      expect(cycleSpread([28, 28])!.spreadDays, 0.0);
      expect(cycleSpread([23, 33])!.spreadDays, 5.0);
    });
  });
}
