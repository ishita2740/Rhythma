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
import '../../services/notification_service.dart';
import '../../utils/date_utils.dart';
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

  void _clearSaveStatus() {
    if (_savedSuccessfully || _saveError != null) {
      setState(() {
        _savedSuccessfully = false;
        _saveError = null;
      });
    }
  }

  Future<void> _onLogSelect(
      DateTime date, String field, LogOption option) async {
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
      newValue =
          existing[field] == option.value ? null : _coerce(field, option.value);
    }

    await LocalStorageService.saveQuickLogField(date, field, newValue);
    _clearSaveStatus();
    if (mounted) context.read<CycleProvider>().refresh();
  }

  Future<void> _saveToBackend(DateTime date) async {
    final log = LocalStorageService.getCycleLogForDate(date) ?? {};
    setState(() {
      _saving = true;
      _saveError = null;
      _savedSuccessfully = false;
    });

    try {
      final synced = await CycleService().submitLog(CycleLog(
        startDate: date,
        flowIntensity: log['flow_intensity'] as String?,
        mood: log['mood'] as String?,
        symptoms: (log['symptoms'] as List?)?.cast<String>(),
        sleepHours: (log['sleep_hours'] as num?)?.toDouble(),
        stressLevel: (log['stress_level'] as num?)?.toInt(),
        waterIntake: (log['water_intake'] as num?)?.toInt(),
        medications: log['medications'] != null
            ? List<Map<String, dynamic>>.from(
                (log['medications'] as List)
                    .map((m) => Map<String, dynamic>.from(m as Map)))
            : null,
      ));
      if (!mounted) return;
      setState(() {
        _saving = false;
        if (synced) {
          _savedSuccessfully = true;
          _saveError = null;
          _saveErrorWasOffline = false;
        } else {
          _saveError = 'offline_queued';
          _saveErrorWasOffline = true;
          _savedSuccessfully = false;
        }
      });

      if (synced && LocalStorageService.periodPredictionReminders) {
        NotificationService.instance.schedulePeriodPredictionReminder();
      }
    } catch (e) {
      if (!mounted) return;

      String errorMessage =
          "Saved on this device, but the server rejected the save.";

      if (e is DioException && e.response?.statusCode == 422) {
        final detail = e.response?.data['detail'];

        if (detail is List && detail.isNotEmpty) {
          errorMessage = detail.first['msg'] ?? errorMessage;
        } else if (detail is String) {
          errorMessage = detail;
        }
      }

      setState(() {
        _saving = false;
        _saveError = errorMessage;
        _saveErrorWasOffline = false;
      });
    }
  }

  dynamic _coerce(String field, String value) {
    if (field == 'sleep_hours') return double.tryParse(value) ?? value;
    if (field == 'stress_level') return int.tryParse(value) ?? value;
    return value;
  }

  String? _formatStoredValue(dynamic raw) {
    if (raw == null) return null;
    if (raw is num) {
      return raw == raw.roundToDouble()
          ? raw.toInt().toString()
          : raw.toString();
    }
    return raw.toString();
  }

  Future<void> _deleteCycleLog() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Entry'),
        content: const Text(
          'Are you sure you want to delete this day\'s log? This cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    if (!mounted) return;
    final cycleProvider = context.read<CycleProvider>();
    final dateKey = RhythmaDateUtils.toDateKey(cycleProvider.selectedDate);
    await LocalStorageService.deleteCycleLog(dateKey);

    try {
      await CycleService().deleteLog(dateKey);
    } catch (_) {}

    if (!mounted) return;
    cycleProvider.refresh();
  }

  Future<void> _setWaterIntake(DateTime date, int glasses) async {
    await LocalStorageService.saveQuickLogField(date, 'water_intake', glasses);
    _clearSaveStatus();
    if (mounted) context.read<CycleProvider>().refresh();
  }

  Future<void> _toggleMedication(DateTime date, String name, bool taken) async {
    final existing = LocalStorageService.getCycleLogForDate(date) ?? {};
    final current = List<Map<String, dynamic>>.from(
        (existing['medications'] as List?)
                ?.map((m) => Map<String, dynamic>.from(m as Map)) ??
            []);
    final idx = current.indexWhere((m) => m['name'] == name);
    if (idx >= 0) {
      current[idx]['taken'] = taken;
    } else {
      current.add({'name': name, 'taken': taken});
    }
    await LocalStorageService.saveQuickLogField(date, 'medications', current);
    _clearSaveStatus();
    if (mounted) context.read<CycleProvider>().refresh();
  }

  Future<void> _addMedication(DateTime date, String name) async {
    if (name.trim().isEmpty) return;
    final existing = LocalStorageService.getCycleLogForDate(date) ?? {};
    final current = List<Map<String, dynamic>>.from(
        (existing['medications'] as List?)
                ?.map((m) => Map<String, dynamic>.from(m as Map)) ??
            []);
    if (current.any((m) => m['name'] == name.trim())) return;
    current.add({'name': name.trim(), 'taken': false});
    await LocalStorageService.saveQuickLogField(date, 'medications', current);
    _clearSaveStatus();
    if (mounted) context.read<CycleProvider>().refresh();
  }

  Future<void> _removeMedication(DateTime date, String name) async {
    final existing = LocalStorageService.getCycleLogForDate(date) ?? {};
    final current = List<Map<String, dynamic>>.from(
        (existing['medications'] as List?)
                ?.map((m) => Map<String, dynamic>.from(m as Map)) ??
            []);
    current.removeWhere((m) => m['name'] == name);
    await LocalStorageService.saveQuickLogField(date, 'medications', current);
    _clearSaveStatus();
    if (mounted) context.read<CycleProvider>().refresh();
  }

  @override
  Widget build(BuildContext context) {
    context.watch<ThemeProvider>();
    final cycleProvider = context.watch<CycleProvider>();
    final l10n = AppLocalizations.of(context)!;

    final displayedMonth = cycleProvider.displayedMonth;
    final selectedDate = cycleProvider.selectedDate;
    final selectedLog =
        LocalStorageService.getCycleLogForDate(selectedDate) ?? {};
    final hasSelections = selectedLog.isNotEmpty;

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
                  label: Text(l10n.cycleToday),
                  style: TextButton.styleFrom(
                    foregroundColor: RhythmaColors.primary,
                  ),
                ),
              ),
            ],
          ),
          GlassCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
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
                CalendarGrid(
                  pageController: _pageController,
                  initialPageOffset: _initialPageOffset,
                ),
                const SizedBox(height: 14),
                Container(height: 1, color: RhythmaColors.border),
                const SizedBox(height: 12),
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
            onSelect: (opt) =>
                _onLogSelect(selectedDate, 'flow_intensity', opt),
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
            color: RhythmaColors.teal,
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
            multiSelectedValues:
                List<String>.from(selectedLog['symptoms'] ?? const []),
            onSelect: (opt) => _onLogSelect(selectedDate, 'symptoms', opt),
          ),

          const SizedBox(height: 16),

          _WaterIntakeRow(
            glasses: (selectedLog['water_intake'] as num?)?.toInt() ?? 0,
            onChanged: (g) => _setWaterIntake(selectedDate, g),
          ),

          const SizedBox(height: 10),

          _MedicationSection(
            date: selectedDate,
            medications: (selectedLog['medications'] as List?)
                    ?.map((m) => Map<String, dynamic>.from(m as Map))
                    .toList() ??
                [],
            onToggle: (name, taken) =>
                _toggleMedication(selectedDate, name, taken),
            onAdd: (name) => _addMedication(selectedDate, name),
            onRemove: (name) => _removeMedication(selectedDate, name),
          ),

          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: !hasSelections || _saving
                  ? null
                  : () => _saveToBackend(selectedDate),
              style: ElevatedButton.styleFrom(
                backgroundColor: RhythmaColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14)),
              ),
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('Save Log',
                      style: TextStyle(fontWeight: FontWeight.w700)),
            ),
          ),
          if (hasSelections) ...[
            const SizedBox(height: 8),
            Center(
              child: TextButton.icon(
                onPressed: _deleteCycleLog,
                icon: const Icon(Icons.delete_outline_rounded, size: 16),
                label: const Text('Delete Log'),
                style: TextButton.styleFrom(
                  foregroundColor: Colors.red,
                ),
              ),
            ),
          ],
          if (_savedSuccessfully) ...[
            const SizedBox(height: 10),
            Row(
              children: const [
                Icon(Icons.check_circle_rounded,
                    color: RhythmaColors.teal, size: 16),
                SizedBox(width: 6),
                Text(
                  'Saved to your account',
                  style: TextStyle(
                      fontSize: 12,
                      color: RhythmaColors.teal,
                      fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ],
          if (_saveError != null) ...[
            const SizedBox(height: 10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.error_outline_rounded,
                    color: RhythmaColors.rose, size: 16),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    _saveErrorWasOffline
                        ? "Saved on this device. Will sync automatically when you're back online."
                        : _saveError!,
                    style:
                        TextStyle(fontSize: 12, color: RhythmaColors.mutedFg),
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
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
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
  final VoidCallback? onTap;
  const _CircleBtn({required this.icon, this.onTap});

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

class _WaterIntakeRow extends StatelessWidget {
  final int glasses;
  final ValueChanged<int> onChanged;
  const _WaterIntakeRow({required this.glasses, required this.onChanged});

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
                  color: RhythmaColors.primary.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.water_drop_outlined,
                    color: RhythmaColors.primary, size: 17),
              ),
              const SizedBox(width: 10),
              Text(
                AppLocalizations.of(context)!.logWaterIntake,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: RhythmaColors.foreground,
                ),
              ),
              const Spacer(),
              _CircleBtn(
                icon: Icons.remove_rounded,
                onTap: glasses > 0 ? () => onChanged(glasses - 1) : null,
              ),
              const SizedBox(width: 10),
              Text(
                '$glasses',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: RhythmaColors.foreground,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                AppLocalizations.of(context)!.logGlasses,
                style: TextStyle(
                  fontSize: 12,
                  color: RhythmaColors.mutedFg,
                ),
              ),
              const SizedBox(width: 10),
              _CircleBtn(
                icon: Icons.add_rounded,
                onTap: () => onChanged(glasses + 1),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MedicationSection extends StatefulWidget {
  final DateTime date;
  final List<Map<String, dynamic>> medications;
  final void Function(String name, bool taken) onToggle;
  final void Function(String name) onAdd;
  final void Function(String name) onRemove;

  const _MedicationSection({
    required this.date,
    required this.medications,
    required this.onToggle,
    required this.onAdd,
    required this.onRemove,
  });

  @override
  State<_MedicationSection> createState() => _MedicationSectionState();
}

class _MedicationSectionState extends State<_MedicationSection> {
  final TextEditingController _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
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
                  color: RhythmaColors.coral.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.medication_outlined,
                    color: RhythmaColors.coral, size: 17),
              ),
              const SizedBox(width: 10),
              Text(
                l10n.logMedications,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: RhythmaColors.foreground,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ...widget.medications.map((med) {
            final name = med['name'] as String;
            final taken = med['taken'] as bool;
            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Checkbox(
                    value: taken,
                    onChanged: (v) =>
                        widget.onToggle(name, v ?? false),
                    activeColor: RhythmaColors.teal,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(4)),
                  ),
                  Expanded(
                    child: Text(
                      name,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                        color: RhythmaColors.foreground,
                        decoration:
                            taken ? TextDecoration.lineThrough : null,
                      ),
                    ),
                  ),
                  GestureDetector(
                    onTap: () => widget.onRemove(name),
                    child: Icon(Icons.close_rounded,
                        size: 18, color: RhythmaColors.mutedFg),
                  ),
                ],
              ),
            );
          }),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  decoration: InputDecoration(
                    hintText: l10n.logAddMedication,
                    hintStyle: TextStyle(
                        fontSize: 13, color: RhythmaColors.mutedFg),
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 10),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide.none,
                    ),
                    filled: true,
                    fillColor: RhythmaColors.surfaceMuted,
                  ),
                  style: TextStyle(
                      fontSize: 13, color: RhythmaColors.foreground),
                  onSubmitted: (v) {
                    widget.onAdd(v);
                    _controller.clear();
                  },
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: () {
                  widget.onAdd(_controller.text);
                  _controller.clear();
                },
                child: Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: RhythmaColors.primary,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.add_rounded,
                      color: Colors.white, size: 20),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
