import 'package:flutter/material.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../config/theme.dart';
import '../services/local_storage_service.dart';

/// Where a date sits in the cycle.
///
/// [overdue] and [unknown] are the two states this provider could not
/// previously express, and they are why this is an enum rather than the
/// bare strings the three phase methods each used to return independently.
/// See [CycleProvider.phaseOf].
///
/// Named `overdue` rather than `late` because `late` is a contextual
/// keyword in Dart. [CycleProvider.phaseKey] still emits the string
/// `'late'`, which is the name `prediction_service.PHASE_LATE` uses on the
/// backend — the wire value and the Dart identifier are allowed to differ,
/// and matching the server matters more here than matching the enum.
enum CyclePhase { period, follicular, ovulation, luteal, overdue, unknown }

/// Flow values that mean bleeding happened.
///
/// `none` is deliberately absent: it is an answer the user gave — "I
/// checked, there was nothing" — and treating it as bleeding would invent
/// a period out of a negative answer. Values are the canonical lowercase
/// keys `LogOptions.flow` persists; comparison lowercases first, because
/// older logs were written with the displayed label ("Medium").
const Set<String> _bleedingFlows = {
  'spotting',
  'light',
  'medium',
  'heavy',
  'very_heavy',
};

/// A missed day inside a period should not split it into two periods.
/// One day of tolerance covers "forgot to log on Tuesday" without merging
/// two genuinely separate bleeds.
const int _periodRunGapToleranceDays = 1;

/// Two period starts closer together than this are not two cycles.
/// Mid-cycle spotting is the case this guards against: without it, one
/// logged spotting day would end the current cycle and start a phantom
/// short one. Matches `prediction_service.MIN_PLAUSIBLE_CYCLE_DAYS` and
/// `trend_service.MIN_DAYS_BETWEEN_PERIOD_STARTS` on the backend.
const int _minDaysBetweenPeriodStarts = 15;

class CycleProvider extends ChangeNotifier {
  final DateTime _today = DateTime.now();

  late DateTime _selectedDate;
  late DateTime _displayedMonth;

  CycleProvider() {
    _selectedDate = DateTime(_today.year, _today.month, _today.day);
    _displayedMonth = DateTime(_today.year, _today.month);
  }

  DateTime get selectedDate => _selectedDate;
  DateTime get displayedMonth => _displayedMonth;

  void selectDate(DateTime date) {
    final today = DateTime(_today.year, _today.month, _today.day);
    final normalized = DateTime(date.year, date.month, date.day);
    if (normalized.isAfter(today)) return; // no logging for future days
    if (_selectedDate != normalized) {
      _selectedDate = normalized;
      notifyListeners();
    }
  }

  void setDisplayedMonth(DateTime month) {
    if (_displayedMonth.year != month.year ||
        _displayedMonth.month != month.month) {
      _displayedMonth = DateTime(month.year, month.month);
      notifyListeners();
    }
  }

  void jumpToToday() {
    _displayedMonth = DateTime(_today.year, _today.month);
    _selectedDate = DateTime(_today.year, _today.month, _today.day);
    notifyListeners();
  }

  /// Whether anything has actually been saved for [date] (Home quick-log
  /// tiles or the Cycle screen's log rows/Save button both write through
  /// LocalStorageService, so this always reflects real data — not a mock).
  bool hasLogsForDate(DateTime date) {
    return LocalStorageService.getCycleLogForDate(date) != null;
  }

  /// Notifies listeners (e.g. to redraw the calendar's "logged" dot) after
  /// a log write elsewhere. The log itself is persisted by whoever calls
  /// this — this provider intentionally doesn't hold log data itself, just
  /// the calendar's navigation/selection state.
  void refresh() => notifyListeners();

  void refreshLogs() {
    notifyListeners();
  }

  // ── Cycle-length settings ────────────────────────────────────────────
  // Read fresh from the profile each time (rather than cached at
  // construction) so edits made on the Profile/Onboarding screens are
  // reflected immediately without having to recreate the provider.

  int get _periodDuration {
    final profile = LocalStorageService.getProfile();
    return (profile?['period_duration'] as num?)?.toInt() ?? 5;
  }

  int get _cycleLength {
    final profile = LocalStorageService.getProfile();
    return (profile?['cycle_length'] as num?)?.toInt() ?? 28;
  }

  static DateTime _dateOnly(DateTime date) =>
      DateTime(date.year, date.month, date.day);

  static DateTime? _parseDay(Object? value) {
    if (value is! String) return null;
    final parsed = DateTime.tryParse(value);
    return parsed == null ? null : _dateOnly(parsed);
  }

  // ── Finding the anchor ───────────────────────────────────────────────

  /// Period start dates reconstructed from logged flow, oldest first.
  ///
  /// There is no "this is a period start" flag in the data — every log
  /// document is keyed by its own day — so a period is reconstructed the
  /// only way the data allows: a run of consecutive bleeding days is a
  /// period, and its first day starts a cycle.
  ///
  /// This is what the old cycle-day calculation ignored entirely. It read
  /// `profile['last_period']` — a single onboarding answer — and nothing
  /// else, so a user who had logged six periods still had her phase
  /// derived from the one date she typed when she signed up.
  List<DateTime> loggedPeriodStarts() {
    final bleeding = <DateTime>[];
    for (final log in LocalStorageService.getCycleLogs()) {
      final flow = (log['flow_intensity'] as String?)?.trim().toLowerCase();
      if (flow == null || !_bleedingFlows.contains(flow)) continue;
      final day = _parseDay(log['start_date']);
      if (day != null) bleeding.add(day);
    }
    if (bleeding.isEmpty) return const [];

    bleeding.sort();

    final starts = <DateTime>[bleeding.first];
    for (var i = 1; i < bleeding.length; i++) {
      final gap = bleeding[i].difference(bleeding[i - 1]).inDays;
      if (gap > _periodRunGapToleranceDays + 1) starts.add(bleeding[i]);
    }

    final merged = <DateTime>[starts.first];
    for (final start in starts.skip(1)) {
      if (start.difference(merged.last).inDays >= _minDaysBetweenPeriodStarts) {
        merged.add(start);
      }
    }
    return merged;
  }

  /// The declared onboarding `last_period`, if it parses.
  DateTime? get declaredLastPeriod {
    final profile = LocalStorageService.getProfile();
    return _parseDay(profile?['last_period']);
  }

  /// The most recent period start on or before [date].
  ///
  /// Precedence matches `prediction_service._last_period_start()` on the
  /// backend: logged history first, the onboarding answer as the
  /// documented fallback. "On or before" matters because the calendar
  /// renders past months — a February day must be measured from the
  /// period that had actually started by February, not from one logged in
  /// June.
  ///
  /// Returns null when there is nothing to measure from, which is a real
  /// answer and not a failure. [phaseOf] turns it into [CyclePhase.unknown]
  /// rather than inventing an anchor.
  DateTime? anchorFor(DateTime date) {
    final target = _dateOnly(date);

    DateTime? best;
    for (final start in loggedPeriodStarts()) {
      if (!start.isAfter(target)) best = start; // ascending, so last wins
    }
    if (best != null) return best;

    final declared = declaredLastPeriod;
    if (declared != null && !declared.isAfter(target)) return declared;
    return null;
  }

  /// Day of cycle for [date], 1-indexed, or null with no anchor.
  ///
  /// **No modulo.** The previous implementation did:
  ///
  /// ```dart
  /// final cycleDay = ((daysSince % cycleLength) + cycleLength) % cycleLength;
  /// return cycleDay + 1;
  /// ```
  ///
  /// which repeats forever with period `cycleLength`. A user who onboarded
  /// in January declaring a 28-day cycle, logged nothing since, and opened
  /// the app in August was shown a fully coloured calendar — seven cycles
  /// synthesised from one January date, with nothing distinguishing that
  /// from a phase computed off a period logged last week.
  ///
  /// Letting the count run past the cycle length is what makes
  /// [CyclePhase.overdue] reachable, and letting it be null is what makes
  /// [CyclePhase.unknown] reachable.
  int? cycleDayFor(DateTime date) {
    final anchor = anchorFor(date);
    if (anchor == null) return null;
    return _dateOnly(date).difference(anchor).inDays + 1;
  }

  // ── Phase ────────────────────────────────────────────────────────────

  /// The phase [date] falls in.
  ///
  /// The one computation. `phaseKey`, `phase` and `phaseColor` each used
  /// to recompute the same three boundaries independently — three copies
  /// of one ladder, which is how the old day-5/13/16 version survived in
  /// three places at once and had to be fixed three times in #316.
  ///
  /// Boundaries past `cycleLength` are [CyclePhase.overdue] rather than
  /// [CyclePhase.luteal], matching `prediction_service.phase_for()` on the
  /// backend so the app and the server cannot disagree about the same day.
  CyclePhase phaseOf(DateTime date) {
    final day = cycleDayFor(date);
    if (day == null || day < 1) return CyclePhase.unknown;

    final cycleLength = _cycleLength;
    if (cycleLength <= 0) return CyclePhase.unknown;

    // Past the expected length, we no longer know where she is. Saying so
    // is both honest and actionable ("log your period"); reporting luteal
    // forever, as the old fallthrough did, is neither.
    if (day > cycleLength) return CyclePhase.overdue;

    final periodEnd = _periodDuration;
    final follicularEnd = (cycleLength / 2).floor() - 2;
    final ovulationEnd = (cycleLength / 2).floor() + 1;

    if (day <= periodEnd) return CyclePhase.period;
    if (day <= follicularEnd) return CyclePhase.follicular;
    if (day <= ovulationEnd) return CyclePhase.ovulation;
    return CyclePhase.luteal;
  }

  /// Stable key for [date]'s phase, for content lookups.
  ///
  /// `menstrual` rather than `period` for the first phase: the Ayurveda
  /// content map in `data/ayurveda_content.dart` is already keyed that
  /// way, and renaming it to match the enum would be churn for no reader's
  /// benefit. `late` and `unknown` have no entry in that map, which is
  /// correct — it falls back to an empty section rather than offering
  /// cycle-phase guidance for a phase we cannot identify.
  String phaseKey(DateTime date) {
    switch (phaseOf(date)) {
      case CyclePhase.period:
        return 'menstrual';
      case CyclePhase.follicular:
        return 'follicular';
      case CyclePhase.ovulation:
        return 'ovulation';
      case CyclePhase.luteal:
        return 'luteal';
      case CyclePhase.overdue:
        return 'late';
      case CyclePhase.unknown:
        return 'unknown';
    }
  }

  String phase(DateTime date, AppLocalizations l10n) {
    switch (phaseOf(date)) {
      case CyclePhase.period:
        return l10n.cyclePhasePeriod;
      case CyclePhase.follicular:
        return l10n.cyclePhaseFollicular;
      case CyclePhase.ovulation:
        return l10n.cyclePhaseOvulation;
      case CyclePhase.luteal:
        return l10n.cyclePhaseLuteal;
      case CyclePhase.overdue:
        return l10n.cyclePhaseLate;
      case CyclePhase.unknown:
        return l10n.cyclePhaseUnknown;
    }
  }

  /// Colour for [date]'s phase.
  ///
  /// `late` and `unknown` are muted rather than alarming. Both mean "we
  /// cannot tell you where you are in your cycle" — a statement about our
  /// confidence, not about her health — and a warning colour on a long
  /// cycle is the risk framing `menstrual_insights_guidelines.md` rules
  /// out. It also stops the calendar looking *more* alive the staler the
  /// data gets, which is what the modulo did.
  Color phaseColor(DateTime date) {
    switch (phaseOf(date)) {
      case CyclePhase.period:
        return RhythmaColors.rose;
      case CyclePhase.follicular:
        return RhythmaColors.primary;
      case CyclePhase.ovulation:
        return RhythmaColors.teal;
      case CyclePhase.luteal:
        return RhythmaColors.coral;
      case CyclePhase.overdue:
      case CyclePhase.unknown:
        return RhythmaColors.mutedFg;
    }
  }
}
