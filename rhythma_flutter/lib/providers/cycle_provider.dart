import 'package:flutter/material.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../config/theme.dart';
import '../services/local_storage_service.dart';

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

  // Phase logic
  String phase(DateTime date, AppLocalizations l10n) {
    final day = date.day;
    if (day <= 5) return l10n.cyclePhasePeriod;
    if (day <= 13) return l10n.cyclePhaseFollicular;
    if (day <= 16) return l10n.cyclePhaseOvulation;
    return l10n.cyclePhaseLuteal;
  }

  Color phaseColor(DateTime date) {
    final day = date.day;
    if (day <= 5) return RhythmaColors.rose;
    if (day <= 13) return RhythmaColors.primary;
    if (day <= 16) return RhythmaColors.teal;
    return RhythmaColors.coral;
  }
}