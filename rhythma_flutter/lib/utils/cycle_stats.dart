/// Descriptive statistics over a user's own logged cycle lengths.
///
/// The Insights screen computed this inline and got the units wrong
/// (issue #522):
///
/// ```dart
/// final variance =
///     lengths.map((v) => (v - mean) * (v - mean)).reduce((a, b) => a + b) / lengths.length;
/// return variance <= 0 ? 0 : variance.round();
/// ```
///
/// The deviations are squared and averaged and the result is never
/// square-rooted, so that is a variance — a quantity in days² — and it was
/// rendered with the word "days" beside it. The error is quadratic, so it
/// is invisible at ±1, mild at ±2 and absurd by ±5: cycles of 26 and 30
/// showed "4 days", and a genuine five-day spread showed "25 days", which
/// is longer than most of the cycles it was describing.
///
/// Worse, the same number decided `isStable = variability <= 3` — a
/// threshold in days applied to a value in days² — which drove four pieces
/// of UI. A woman with 26- and 30-day cycles scored 4, failed the test,
/// and was shown "Moderate" in a warning colour for cycles about as
/// regular as real ones get.
///
/// This is a port of `web/src/lib/cycleStats.ts`, which fixed the same
/// mistake in the web app's Profile page under issue #383. It is a port
/// rather than a fresh implementation on purpose: the two platforms were
/// reporting different variability figures for the same account, and the
/// only way that stays fixed is if they run the same arithmetic.
///
/// **On the choice of statistic.** Mean absolute deviation rather than a
/// standard deviation, because the label reads `±N days` and that is what
/// a reader takes it to mean: "my cycles are usually about this far from
/// my average". A standard deviation answers a subtly different question,
/// and on the handful of cycles a user has logged the difference between
/// them is far smaller than the difference between either and what was
/// being shown. What matters is that the number is in days, measured from
/// this user's own average.
library;

/// How steady a user's cycles are, and what that is based on.
class CycleSpread {
  /// Mean cycle length across the samples, in days, to one decimal.
  final double meanDays;

  /// Typical distance of a cycle from that mean, in days, to one decimal.
  ///
  /// Zero for a user whose cycles are all the same length — a real and
  /// correct answer, not a missing one.
  final double spreadDays;

  /// How many cycles the two figures above are based on.
  final int sampleSize;

  const CycleSpread({
    required this.meanDays,
    required this.spreadDays,
    required this.sampleSize,
  });

  /// [spreadDays] without a pointless trailing `.0`.
  ///
  /// The figure is rounded to one decimal, so a whole number of days
  /// arrives as `2.0` and would otherwise be shown as "±2.0 days" beside
  /// "±2.5 days" for a user whose spread happens not to be whole.
  String get spreadLabel => _trimZero(spreadDays);

  /// [meanDays] in the same form.
  String get meanLabel => _trimZero(meanDays);

  /// Value equality, so two spreads computed from equivalent inputs
  /// compare equal — a filtered list and the already-clean list it reduces
  /// to describe the same cycles and should not be distinguishable.
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is CycleSpread &&
          other.meanDays == meanDays &&
          other.spreadDays == spreadDays &&
          other.sampleSize == sampleSize;

  @override
  int get hashCode => Object.hash(meanDays, spreadDays, sampleSize);

  @override
  String toString() =>
      'CycleSpread(mean: $meanDays, spread: $spreadDays, n: $sampleSize)';
}

/// Cycles at or below this distance from the user's own mean read as
/// steady.
///
/// Three days, applied to a value that is now genuinely in days. The old
/// `variability <= 3` used the same number against a variance, so it was
/// really asking whether the spread was under about 1.7 days.
const double kSteadyCycleSpreadDays = 3.0;

String _trimZero(double value) {
  final rounded = value.toStringAsFixed(1);
  return rounded.endsWith('.0')
      ? rounded.substring(0, rounded.length - 2)
      : rounded;
}

double _roundTo1(double value) => (value * 10).round() / 10;

/// Drop anything that is not a usable number of days.
///
/// `_cycleLengthTrend` is built from the `/dashboard` payload, and a
/// partially-written log or a serialization slip can put a zero or a
/// negative in it. One of those drags the mean without being visible as an
/// error, so it costs one sample here instead of the whole tile.
///
/// The web module also screens for `NaN` and infinities. There is no
/// equivalent to screen for here: the list arrives as `List<int>`, built
/// by `.whereType<num>().map((n) => n.toInt())`, so the only bad values
/// that survive that are non-positive ones.
List<int> usableLengths(Iterable<int> values) =>
    values.where((value) => value > 0).toList();

/// Arithmetic mean of the usable lengths, or `null` when there are none.
double? meanOf(Iterable<int> values) {
  final usable = usableLengths(values);
  if (usable.isEmpty) return null;
  return usable.reduce((total, value) => total + value) / usable.length;
}

/// How much this user's cycles vary, measured against her own average.
///
/// Returns `null` when there is nothing meaningful to report — fewer than
/// two usable cycles. One cycle has no spread, and reporting a figure for
/// it states something the data does not support. The old code returned
/// `0` here, which reads as "perfectly regular" and was fed straight into
/// the stability verdict, so a user who had logged nothing was told her
/// cycles were healthy and stabilising.
CycleSpread? cycleSpread(Iterable<int> lengths) {
  final usable = usableLengths(lengths);
  if (usable.length < 2) return null;

  final mean = usable.reduce((total, value) => total + value) / usable.length;
  final meanAbsoluteDeviation =
      usable.map((value) => (value - mean).abs()).reduce((a, b) => a + b) /
          usable.length;

  return CycleSpread(
    meanDays: _roundTo1(mean),
    spreadDays: _roundTo1(meanAbsoluteDeviation),
    sampleSize: usable.length,
  );
}

/// Whether [spread] is steady enough to describe as such.
///
/// `null` — not `false` — when there is no spread to judge. The three
/// states are genuinely different: steady, variable, and "not enough
/// logged yet to say", and collapsing the third into either of the others
/// puts a verdict in front of a user that her data does not support.
bool? isSteadyCycle(CycleSpread? spread) {
  if (spread == null) return null;
  return spread.spreadDays <= kSteadyCycleSpreadDays;
}
