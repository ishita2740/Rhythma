import 'package:flutter/material.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../config/theme.dart';
import '../services/local_storage_service.dart';

class CycleProvider extends ChangeNotifier {
  /// How this provider asks what day it is.
  ///
  /// Injectable so a test can step across midnight instead of waiting for
  /// it. Before this existed there was no seam at all — the class called
  /// `DateTime.now()` directly, which is why the existing future-date test
  /// had to phrase itself as `DateTime.now().add(...)`.
  final DateTime Function() _clock;

  late DateTime _selectedDate;
  late DateTime _displayedMonth;

  /// The last day [refreshIfDayChanged] observed, so a rollover can be
  /// detected without notifying listeners on every resume.
  late DateTime _lastKnownDay;

  CycleProvider({DateTime Function()? clock}) : _clock = clock ?? DateTime.now {
    final startOfToday = today;
    _selectedDate = startOfToday;
    _displayedMonth = DateTime(startOfToday.year, startOfToday.month);
    _lastKnownDay = startOfToday;
  }

  /// Midnight of the current day, resolved fresh on every read.
  ///
  /// This used to be `final DateTime _today = DateTime.now()`, captured once
  /// in a field initialiser — and `main.dart` builds this provider once for
  /// the lifetime of the process. A backgrounded app is not killed on any
  /// schedule the user controls, so `_today` was "whatever day it was when
  /// Rhythma last cold-started".
  ///
  /// `CalendarGrid` called `DateTime.now()` itself, so the grid stayed
  /// current while the provider did not. They disagreed silently: the grid
  /// drew today's cell as tappable, the tap called [selectDate], and
  /// [selectDate] rejected it as a future date against a stale "today". The
  /// tap did nothing at all — no selection, no error — until the app was
  /// force-quit.
  ///
  /// The grid now reads this getter rather than the clock, so there is one
  /// answer to "what day is it" on this screen instead of two.
  DateTime get today {
    final now = _clock();
    return DateTime(now.year, now.month, now.day);
  }

  DateTime get selectedDate => _selectedDate;
  DateTime get displayedMonth => _displayedMonth;

  void selectDate(DateTime date) {
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
    final startOfToday = today;
    _displayedMonth = DateTime(startOfToday.year, startOfToday.month);
    _selectedDate = startOfToday;
    _lastKnownDay = startOfToday;
    notifyListeners();
  }

  /// Repaint if the date has changed since this was last checked.
  ///
  /// Resolving [today] per call fixes the *behaviour* — a tap on today's
  /// cell is accepted again — but it does not repaint a screen that is
  /// already on top when the date changes underneath it. The today ring
  /// would sit on yesterday until something else triggered a rebuild.
  ///
  /// `CycleScreen` calls this when the app resumes, which is the moment
  /// that matters and the one we can actually observe. Returns whether the
  /// day had in fact changed, so a caller can do more than repaint.
  bool refreshIfDayChanged() {
    final startOfToday = today;
    if (startOfToday == _lastKnownDay) return false;

    // The selection follows the date only when it was pinned to what used
    // to be today. A user who deliberately selected an earlier day and
    // left the app open should come back to the day she chose.
    final selectionWasToday = _selectedDate == _lastKnownDay;
    // Likewise the month: a user parked on "this month" should still be on
    // this month, not on the one that just ended. A month she navigated to
    // deliberately is left where she put it.
    final monthWasCurrent = _displayedMonth.year == _lastKnownDay.year &&
        _displayedMonth.month == _lastKnownDay.month;

    _lastKnownDay = startOfToday;
    if (selectionWasToday) {
      _selectedDate = startOfToday;
    }
    if (monthWasCurrent) {
      _displayedMonth = DateTime(startOfToday.year, startOfToday.month);
    }
    notifyListeners();
    return true;
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

  /// Day-of-cycle for [date], counted from the saved `last_period` start
  /// date (1-indexed, wraps across multiple cycle lengths). Falls back to
  /// the plain day-of-month when no `last_period` has been saved yet.
  int _getCycleDay(DateTime date) {
    final profile = LocalStorageService.getProfile();
    final lastPeriodStr = profile?['last_period'] as String?;
    if (lastPeriodStr == null) return date.day;

    final lastPeriod = DateTime.tryParse(lastPeriodStr);
    if (lastPeriod == null) return date.day;

    final normalizedStart =
        DateTime(lastPeriod.year, lastPeriod.month, lastPeriod.day);
    final normalizedDate = DateTime(date.year, date.month, date.day);

    final daysSince = normalizedDate.difference(normalizedStart).inDays;
    final cycleLength = _cycleLength;
    if (cycleLength <= 0) return date.day;

    // Modulo that stays positive even if `date` falls before `last_period`.
    final cycleDay = ((daysSince % cycleLength) + cycleLength) % cycleLength;
    return cycleDay + 1;
  }

  // Phase logic
  String phaseKey(DateTime date) {
    final day = _getCycleDay(date);
    final periodEnd = _periodDuration;
    final follicularEnd = (_cycleLength / 2).floor() - 2;
    final ovulationEnd = (_cycleLength / 2).floor() + 1;

    if (day <= periodEnd) return 'menstrual';
    if (day <= follicularEnd) return 'follicular';
    if (day <= ovulationEnd) return 'ovulation';
    return 'luteal';
  }

  String phase(DateTime date, AppLocalizations l10n) {
    final day = _getCycleDay(date);
    final periodEnd = _periodDuration;
    final follicularEnd = (_cycleLength / 2).floor() - 2;
    final ovulationEnd = (_cycleLength / 2).floor() + 1;

    if (day <= periodEnd) return l10n.cyclePhasePeriod;
    if (day <= follicularEnd) return l10n.cyclePhaseFollicular;
    if (day <= ovulationEnd) return l10n.cyclePhaseOvulation;
    return l10n.cyclePhaseLuteal;
  }

  Color phaseColor(DateTime date) {
    final day = _getCycleDay(date);
    final periodEnd = _periodDuration;
    final follicularEnd = (_cycleLength / 2).floor() - 2;
    final ovulationEnd = (_cycleLength / 2).floor() + 1;

    if (day <= periodEnd) return RhythmaColors.rose;
    if (day <= follicularEnd) return RhythmaColors.primary;
    if (day <= ovulationEnd) return RhythmaColors.teal;
    return RhythmaColors.coral;
  }
}
