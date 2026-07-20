/// Mirrors the backend's `CycleLog` Pydantic model (see
/// `backend/api/cycle.py`). Used both for a full Cycle-screen "Save"
/// submission (most fields set) and a partial Home-tile quick-log
/// submission (only the one field being tapped set) — `toJson()` omits
/// null fields either way, and the backend's `POST /cycle/log` upserts
/// only the fields it receives into that day's log document.
class CycleLog {
  final DateTime startDate;
  final DateTime? endDate;
  final String? flowIntensity;
  final String? mood;
  final List<String>? symptoms;
  final double? sleepHours;
  final int? stressLevel;
  final String? notes;

  const CycleLog({
    required this.startDate,
    this.endDate,
    this.flowIntensity,
    this.mood,
    this.symptoms,
    this.sleepHours,
    this.stressLevel,
    this.notes,
  });

  Map<String, dynamic> toJson() => {
        'start_date': _dateStr(startDate),
        if (endDate != null) 'end_date': _dateStr(endDate!),
        if (flowIntensity != null) 'flow_intensity': flowIntensity,
        if (mood != null) 'mood': mood,
        if (symptoms != null) 'symptoms': symptoms,
        if (sleepHours != null) 'sleep_hours': sleepHours,
        if (stressLevel != null) 'stress_level': stressLevel,
        if (notes != null) 'notes': notes,
      };

  factory CycleLog.fromMap(Map<String, dynamic> map) => CycleLog(
        startDate: DateTime.parse(map['start_date'].toString()),
        endDate: map['end_date'] != null
            ? DateTime.tryParse(map['end_date'].toString())
            : null,
        flowIntensity: map['flow_intensity'] as String?,
        mood: map['mood'] as String?,
        symptoms: map['symptoms'] != null
            ? List<String>.from(map['symptoms'] as List)
            : null,
        sleepHours: (map['sleep_hours'] as num?)?.toDouble(),
        stressLevel: (map['stress_level'] as num?)?.toInt(),
        notes: map['notes'] as String?,
      );

  /// A copy with one field overridden — handy for building up a day's log
  /// incrementally (e.g. merging a newly-tapped field into what's already
  /// locally saved for that day) without repeating every field.
  CycleLog copyWith({
    String? flowIntensity,
    String? mood,
    List<String>? symptoms,
    double? sleepHours,
    int? stressLevel,
    String? notes,
  }) =>
      CycleLog(
        startDate: startDate,
        endDate: endDate,
        flowIntensity: flowIntensity ?? this.flowIntensity,
        mood: mood ?? this.mood,
        symptoms: symptoms ?? this.symptoms,
        sleepHours: sleepHours ?? this.sleepHours,
        stressLevel: stressLevel ?? this.stressLevel,
        notes: notes ?? this.notes,
      );

  static String _dateStr(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}