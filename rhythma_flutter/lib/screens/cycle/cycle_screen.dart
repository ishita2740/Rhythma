import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'package:dio/dio.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../components/shared.dart';
import '../../models/cycle_log.dart';
import '../../providers/theme_provider.dart';
import '../../providers/cycle_provider.dart';
import '../../services/cycle_service.dart';
import '../../services/local_storage_service.dart';
import '../../utils/log_options.dart';
import 'components/calendar_grid.dart';

class CycleScreen extends StatefulWidget {
  const CycleScreen({super.key});

  @override
  State<CycleScreen> createState() => _CycleScreenState();
}

class _CycleScreenState extends State<CycleScreen> {
  static const int _initialPageOffset = 12000;
  late final PageController _pageController;

  // Save-button state for the backend sync. Local (Hive) saves on every
  // log-row tap regardless of this — this only tracks the explicit "Save"
  // submission of the full day's log to the backend.
  bool _saving = false;
  bool _savedSuccessfully = false;
  String? _saveError;
  bool _saveErrorWasOffline = false;

  @override
  void initState() {
    super.initState();
    _pageController = PageController(initialPage: _initialPageOffset);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _goToPreviousMonth() {
    _pageController.previousPage(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  void _goToNextMonth() {
    _pageController.nextPage(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  void _jumpToToday() {
    context.read<CycleProvider>().jumpToToday();
    _pageController.animateToPage(
      _initialPageOffset,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  /// Every edit after a successful save (or a day change) clears the
  /// "Saved to your account" confirmation, since the on-screen selection
  /// and the backend are out of sync again until Save is tapped.
  void _clearSaveStatus() {
    if (_savedSuccessfully || _saveError != null) {
      setState(() {
        _savedSuccessfully = false;
        _saveError = null;
      });
    }
  }

  Future<void> _onLogSelect(DateTime date, String field, LogOption option) async {
    final existing = LocalStorageService.getCycleLogForDate(date) ?? {};

    dynamic newValue;
    if (field == 'symptoms') {
      final current = List<String>.from(existing['symptoms'] ?? []);
      if (current.contains(option.value)) {
        current.remove(option.value);
      } else {
        current.add(option.value);
      }
      newValue = current;
    } else {
      // Tapping the already-selected chip again clears that field.
      newValue = existing[field] == option.value ? null : _coerce(field, option.value);
    }

    await LocalStorageService.saveQuickLogField(date, field, newValue);
    _clearSaveStatus();
    // Local-only state (the calendar's "logged" dot, the log rows below)
    // lives in Hive, not this provider — notify so watchers rebuild with
    // the freshly-saved value.
    if (mounted) context.read<CycleProvider>().refresh();
  }

  /// Builds a CycleLog from everything currently saved for [date] and
  /// submits it to the backend via `POST /cycle/log`.
  Future<void> _saveToBackend(DateTime date) async {
    final log = LocalStorageService.getCycleLogForDate(date) ?? {};
    setState(() {
      _saving = true;
      _saveError = null;
      _savedSuccessfully = false;
    });

    try {
      await CycleService().submitLog(CycleLog(
        startDate: date,
        flowIntensity: log['flow_intensity'] as String?,
        mood: log['mood'] as String?,
        symptoms: (log['symptoms'] as List?)?.cast<String>(),
        sleepHours: (log['sleep_hours'] as num?)?.toDouble(),
        stressLevel: (log['stress_level'] as num?)?.toInt(),
      ));
      if (!mounted) return;
      setState(() {
        _saving = false;
        _savedSuccessfully = true;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _saveError = e.toString();
        _saveErrorWasOffline = e is DioException &&
            (e.type == DioExceptionType.connectionError ||
                e.type == DioExceptionType.connectionTimeout ||
                e.type == DioExceptionType.receiveTimeout ||
                e.type == DioExceptionType.sendTimeout ||
                e.type == DioExceptionType.unknown);
      });
    }
  }

  /// Converts a LogOption's canonical string value into the type the
  /// backend's CycleLog model expects for that field.
  dynamic _coerce(String field, String value) {
    if (field == 'sleep_hours') return double.tryParse(value) ?? value;
    if (field == 'stress_level') return int.tryParse(value) ?? value;
    return value;
  }

  /// LogOptions.sleep uses canonical strings like '4' and '9.5'. A value
  /// round-tripped through Hive as a double (e.g. 6.0) wouldn't otherwise
  /// match the option's value ("6") — this reformats so a previously-saved
  /// chip still shows as selected.
  String? _formatStoredValue(dynamic raw) {
    if (raw == null) return null;
    if (raw is num) {
      return raw == raw.roundToDouble() ? raw.toInt().toString() : raw.toString();
    }
    return raw.toString();
  }

  @override
  Widget build(BuildContext context) {
    context.watch<ThemeProvider>();
    final cycleProvider = context.watch<CycleProvider>();
    final l10n = AppLocalizations.of(context)!;

    final displayedMonth = cycleProvider.displayedMonth;
    final selectedDate = cycleProvider.selectedDate;
    final selectedLog = LocalStorageService.getCycleLogForDate(selectedDate) ?? {};
    final hasSelections = selectedLog.isNotEmpty;

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: _ScreenHeader(
                  title: l10n.cycleTrackerTitle,
                  subtitle: DateFormat('MMMM yyyy').format(displayedMonth),
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: TextButton.icon(
                  onPressed: _jumpToToday,
                  icon: const Icon(Icons.today_rounded, size: 16),
                  label: const Text('Today'),
                  style: TextButton.styleFrom(
                    foregroundColor: RhythmaColors.primary,
                  ),
                ),
              ),
            ],
          ),

          // Calendar card
          GlassCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                // Month nav
                Row(
                  children: [
                    _CircleBtn(
                        icon: Icons.chevron_left_rounded,
                        onTap: _goToPreviousMonth),
                    Expanded(
                      child: Center(
                        child: Text(
                          DateFormat('MMMM yyyy').format(displayedMonth),
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: RhythmaColors.foreground,
                          ),
                        ),
                      ),
                    ),
                    _CircleBtn(
                        icon: Icons.chevron_right_rounded,
                        onTap: _goToNextMonth),
                  ],
                ),
                const SizedBox(height: 14),

                // Weekday headers
                Row(
                  children: ['S', 'M', 'T', 'W', 'T', 'F', 'S']
                      .map((d) => Expanded(
                            child: Center(
                              child: Text(
                                d,
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                  color: RhythmaColors.mutedFg,
                                ),
                              ),
                            ),
                          ))
                      .toList(),
                ),
                const SizedBox(height: 8),

                // Days grid using the existing CalendarGrid
                CalendarGrid(
                  pageController: _pageController,
                  initialPageOffset: _initialPageOffset,
                ),

                const SizedBox(height: 14),
                Container(height: 1, color: RhythmaColors.border),
                const SizedBox(height: 12),

                // Legend
                Wrap(
                  spacing: 14,
                  runSpacing: 6,
                  children: [
                    _Legend(l10n.cyclePhasePeriod, RhythmaColors.rose),
                    _Legend(l10n.cyclePhaseFollicular, RhythmaColors.primary),
                    _Legend(l10n.cyclePhaseOvulation, RhythmaColors.teal),
                    _Legend(l10n.cyclePhaseLuteal, RhythmaColors.coral),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 18),

          // Log section
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              '${l10n.logFor} ${DateFormat('MMM').format(selectedDate)} ${selectedDate.day} · ${cycleProvider.phase(selectedDate, l10n)}',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: RhythmaColors.foreground,
              ),
            ),
          ),
          _LogRow(
            icon: Icons.water_drop_outlined,
            label: l10n.homeLogFlow,
            options: LogOptions.flow(l10n),
            color: RhythmaColors.rose,
            selectedValue: selectedLog['flow_intensity'] as String?,
            onSelect: (opt) => _onLogSelect(selectedDate, 'flow_intensity', opt),
          ),
          const SizedBox(height: 10),
          _LogRow(
            icon: Icons.sentiment_satisfied_alt_rounded,
            label: l10n.homeLogMood,
            options: LogOptions.mood,
            color: RhythmaColors.coral,
            selectedValue: selectedLog['mood'] as String?,
            onSelect: (opt) => _onLogSelect(selectedDate, 'mood', opt),
          ),
          const SizedBox(height: 10),
          _LogRow(
            icon: Icons.bolt_rounded,
            label: l10n.logLabelEnergy,
            options: LogOptions.stress(l10n),
            color: RhythmaColors.primary,
            selectedValue: selectedLog['stress_level']?.toString(),
            onSelect: (opt) => _onLogSelect(selectedDate, 'stress_level', opt),
          ),
          const SizedBox(height: 10),
          _LogRow(
            icon: Icons.bedtime_outlined,
            label: l10n.homeLogSleep,
            options: LogOptions.sleep(l10n),
            color: RhythmaColors.primary,
            selectedValue: _formatStoredValue(selectedLog['sleep_hours']),
            onSelect: (opt) => _onLogSelect(selectedDate, 'sleep_hours', opt),
          ),
          const SizedBox(height: 10),
          _LogRow(
            icon: Icons.psychology_outlined,
            label: l10n.logLabelSymptoms,
            options: LogOptions.symptoms(l10n),
            color: RhythmaColors.teal,
            multiSelectedValues: List<String>.from(selectedLog['symptoms'] ?? const []),
            onSelect: (opt) => _onLogSelect(selectedDate, 'symptoms', opt),
          ),

          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: !hasSelections || _saving ? null : () => _saveToBackend(selectedDate),
              style: ElevatedButton.styleFrom(
                backgroundColor: RhythmaColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              ),
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('Save Log', style: TextStyle(fontWeight: FontWeight.w700)),
            ),
          ),
          if (_savedSuccessfully) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                Icon(Icons.check_circle_rounded, color: RhythmaColors.teal, size: 16),
                const SizedBox(width: 6),
                Text(
                  'Saved to your account',
                  style: TextStyle(fontSize: 12, color: RhythmaColors.teal, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ],
          if (_saveError != null) ...[
            const SizedBox(height: 10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.error_outline_rounded, color: RhythmaColors.rose, size: 16),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    _saveErrorWasOffline
                        ? "Saved on this device, but couldn't reach the server yet. Try again once you're back online."
                        : "Saved on this device, but the server rejected the save. Try again in a bit.",
                    style: TextStyle(fontSize: 12, color: RhythmaColors.mutedFg),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _LogRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final List<LogOption> options;
  final Color color;
  final String? selectedValue;
  final List<String>? multiSelectedValues;
  final ValueChanged<LogOption> onSelect;

  const _LogRow({
    required this.icon,
    required this.label,
    required this.options,
    required this.color,
    required this.onSelect,
    this.selectedValue,
    this.multiSelectedValues,
  });

  bool _isSelected(LogOption opt) => multiSelectedValues != null
      ? multiSelectedValues!.contains(opt.value)
      : selectedValue == opt.value;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 17),
              ),
              const SizedBox(width: 10),
              Text(
                label,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: RhythmaColors.foreground,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: options.map((opt) {
              final sel = _isSelected(opt);
              return GestureDetector(
                onTap: () => onSelect(opt),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 160),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                  decoration: BoxDecoration(
                    color: sel ? color : RhythmaColors.surfaceMuted,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    opt.label,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: sel ? Colors.white : RhythmaColors.foreground,
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  final String label;
  final Color color;
  const _Legend(this.label, this.color);

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 5),
        Text(label,
            style: TextStyle(
                fontSize: 12,
                color: RhythmaColors.mutedFg,
                fontWeight: FontWeight.w500)),
      ],
    );
  }
}

class _CircleBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  const _CircleBtn({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 34,
        height: 34,
        decoration: BoxDecoration(
          color: RhythmaColors.surfaceMuted,
          borderRadius: BorderRadius.circular(17),
        ),
        child: Icon(icon, size: 18, color: RhythmaColors.foreground),
      ),
    );
  }
}

class _ScreenHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  const _ScreenHeader({required this.title, this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 8, 2, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.w700,
                color: RhythmaColors.foreground,
              )),
          if (subtitle != null) ...[
            const SizedBox(height: 2),
            Text(subtitle!,
                style: TextStyle(fontSize: 13, color: RhythmaColors.mutedFg)),
          ],
        ],
      ),
    );
  }
}
