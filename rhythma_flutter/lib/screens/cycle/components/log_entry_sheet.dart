import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../../providers/cycle_provider.dart';
import '../../../services/cycle_service.dart';
import '../../../services/local_storage_service.dart';
import '../../../utils/date_utils.dart';
import '../../../utils/log_options.dart';

class LogEntrySheet extends StatefulWidget {
  final DateTime date;
  final Map<String, dynamic>? existingLog;

  const LogEntrySheet({
    super.key,
    required this.date,
    this.existingLog,
  });

  static Future<void> show(BuildContext context, DateTime date,
      {Map<String, dynamic>? existingLog}) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => LogEntrySheet(date: date, existingLog: existingLog),
    );
  }

  @override
  State<LogEntrySheet> createState() => _LogEntrySheetState();
}

class _LogEntrySheetState extends State<LogEntrySheet> {
  String? _flowIntensity;
  String? _mood;
  double _sleepHours = 8.0;
  double _stressLevel = 1.0;
  List<String> _symptoms = [];

  final List<String> _moodEmojis = ['😀', '😌', '😐', '😔', '😢', '😡'];

  @override
  void initState() {
    super.initState();
    if (widget.existingLog != null) {
      final log = widget.existingLog!;
      _flowIntensity = log['flow_intensity'] as String?;
      _mood = log['mood'] as String?;
      _sleepHours = ((log['sleep_hours'] as num?)?.toDouble() ?? 8.0).clamp(2.0, 14.0);
      _stressLevel = (log['stress_level'] as num?)?.toDouble() ?? 1.0;
      if (log['symptoms'] != null) {
        _symptoms = List<String>.from(log['symptoms'] as List);
      }
    }
  }

  void _saveLog() {
    final log = {
      if (widget.existingLog != null) ...widget.existingLog!,
      'start_date': RhythmaDateUtils.toDateKey(widget.date),
      if (_flowIntensity != null) 'flow_intensity': _flowIntensity,
      if (_mood != null) 'mood': _mood,
      'sleep_hours': _sleepHours,
      'stress_level': _stressLevel,
      'symptoms': _symptoms,
    };
    LocalStorageService.saveCycleLog(log);
    Navigator.of(context).pop();
  }

  Future<void> _deleteLog() async {
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

    final dateKey = RhythmaDateUtils.toDateKey(widget.date);
    await LocalStorageService.deleteCycleLog(dateKey);

    // Best-effort backend sync — don't block the UI if it fails.
    try {
      await CycleService().deleteLog(dateKey);
    } catch (_) {
      // Local delete succeeded; backend sync will retry via Firestore.
    }

    if (!mounted) return;
    context.read<CycleProvider>().refresh();
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final theme = Theme.of(context);

    return DraggableScrollableSheet(
      initialChildSize: 0.9,
      minChildSize: 0.5,
      maxChildSize: 0.9,
      expand: false,
      builder: (context, scrollController) {
        return Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    l10n.logTitle,
                    style: theme.textTheme.headlineSmall
                        ?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  Row(
                    children: [
                      if (widget.existingLog != null)
                        IconButton(
                          icon: const Icon(Icons.delete_outline_rounded),
                          color: Colors.red,
                          tooltip: 'Delete entry',
                          onPressed: _deleteLog,
                        ),
                      IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => Navigator.of(context).pop(),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Expanded(
                child: ListView(
                  controller: scrollController,
                  children: [
                    // Flow Intensity
                    Text(l10n.logFlowIntensity,
                        style: theme.textTheme.titleMedium),
                    const SizedBox(height: 8),
                    SegmentedButton<String>(
                      segments: LogOptions.flow(l10n)
                          .where((o) => o.value != 'none')
                          .map((option) => ButtonSegment(
                              value: option.value,
                              label: Text(option.label)))
                          .toList(),
                      selected: _flowIntensity != null
                          ? {_flowIntensity!}
                          : <String>{},
                      onSelectionChanged: (Set<String> newSelection) {
                        setState(() {
                          _flowIntensity = newSelection.first;
                        });
                      },
                      emptySelectionAllowed: true,
                    ),
                    const SizedBox(height: 24),

                    // Mood
                    Text(l10n.logMood, style: theme.textTheme.titleMedium),
                    const SizedBox(height: 8),
                    SizedBox(
                      height: 60,
                      child: ListView.builder(
                        scrollDirection: Axis.horizontal,
                        itemCount: _moodEmojis.length,
                        itemBuilder: (context, index) {
                          final emoji = _moodEmojis[index];
                          final isSelected = _mood == emoji;
                          return GestureDetector(
                            onTap: () {
                              setState(() {
                                _mood = isSelected ? null : emoji;
                              });
                            },
                            child: Container(
                              margin: const EdgeInsets.only(right: 12),
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: isSelected
                                    ? theme.colorScheme.primaryContainer
                                    : theme.colorScheme.surfaceContainerHighest,
                                shape: BoxShape.circle,
                                border: isSelected
                                    ? Border.all(
                                        color: theme.colorScheme.primary,
                                        width: 2)
                                    : null,
                              ),
                              child: Center(
                                child: Text(emoji,
                                    style: const TextStyle(fontSize: 24)),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Sleep Hours
                    Text('${l10n.logSleepHours}: ${_sleepHours.toInt()}h',
                        style: theme.textTheme.titleMedium),
                    Slider(
                      value: _sleepHours,
                      min: 2,
                      max: 14,
                      divisions: 12,
                      label: _sleepHours.toInt().toString(),
                      onChanged: (value) {
                        setState(() {
                          _sleepHours = value;
                        });
                      },
                    ),
                    const SizedBox(height: 16),

                    // Stress Level
                    Text('${l10n.logStressLevel}: ${_stressLevel.toInt()}',
                        style: theme.textTheme.titleMedium),
                    Slider(
                      value: _stressLevel,
                      min: 1,
                      max: 5,
                      divisions: 4,
                      label: _stressLevel.toInt().toString(),
                      onChanged: (value) {
                        setState(() {
                          _stressLevel = value;
                        });
                      },
                    ),
                    const SizedBox(height: 16),

                    // Symptoms
                    Text(l10n.logLabelSymptoms,
                        style: theme.textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _buildSymptomChip('Cramps', l10n.logSympCramps),
                        _buildSymptomChip('Headache', l10n.logSympHeadache),
                        _buildSymptomChip('Bloating', l10n.logSympBloating),
                        _buildSymptomChip('Fatigue', l10n.logSympFatigue),
                        _buildSymptomChip('Nausea', l10n.logSympNausea),
                        _buildSymptomChip('Acne', l10n.logSympAcne),
                        _buildSymptomChip('Back Pain', l10n.logSympBackPain),
                        _buildSymptomChip('severe pain', l10n.logSympSeverePain ?? 'Severe Pain'),
                        _buildSymptomChip('fainting', l10n.logSympFainting ?? 'Fainting'),
                      ],
                    ),
                    const SizedBox(height: 40),
                  ],
                ),
              ),
              ElevatedButton(
                onPressed: _saveLog,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: Text(l10n.logSave),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSymptomChip(String id, String label) {
    final isSelected = _symptoms.contains(id);
    return FilterChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (selected) {
        setState(() {
          if (selected) {
            _symptoms.add(id);
          } else {
            _symptoms.remove(id);
          }
        });
      },
    );
  }
}
