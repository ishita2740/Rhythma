import 'package:rhythma/l10n/app_localizations.dart';

/// A single tappable log option: [label] is the localized text shown to the
/// user, [value] is a fixed, locale-independent key that gets persisted
/// locally and sent to the backend. Without this split, saving the literal
/// displayed string (e.g. "हल्का" for "Light" in Hindi) would mean the
/// backend's flow-intensity/CVI scoring — which matches against fixed
/// English keywords — silently stopped working for non-English users.
class LogOption {
  final String label;
  final String value;
  const LogOption(this.label, this.value);
}

/// Canonical option sets for each quick-loggable field, shared by the Home
/// screen's quick-log sheet and the Cycle screen's detailed log rows so
/// both write the same values for the same field.
class LogOptions {
  static List<LogOption> flow(AppLocalizations l10n) => [
        LogOption(l10n.logNone, 'none'),
        LogOption(l10n.logLight, 'light'),
        LogOption(l10n.logMedium, 'medium'),
        LogOption(l10n.logHeavy, 'heavy'),
      ];

  static const List<LogOption> mood = [
    LogOption('😊', 'happy'),
    LogOption('😐', 'neutral'),
    LogOption('😔', 'sad'),
    LogOption('😤', 'frustrated'),
    LogOption('🥰', 'loved'),
  ];

  /// Sleep hours, stored as a representative numeric value (string form —
  /// converted to a real number right before it's sent to the backend).
  static List<LogOption> sleep(AppLocalizations l10n) => [
        LogOption(l10n.logSleep1, '4'),
        LogOption(l10n.logSleep2, '6'),
        LogOption(l10n.logSleep3, '8'),
        LogOption(l10n.logSleep4, '9.5'),
      ];

  /// Backed by the `stress_level` field. Mapped onto a 1–5 scale (matching
  /// the range the backend's MHS model comments describe) rather than the
  /// UI's 3 buckets 1:1.
  static List<LogOption> stress(AppLocalizations l10n) => [
        LogOption(l10n.logEnergyLow, '1'),
        LogOption(l10n.logEnergyMid, '3'),
        LogOption(l10n.logEnergyHigh, '5'),
      ];

  static List<LogOption> symptoms(AppLocalizations l10n) => [
        LogOption(l10n.logSympCramps, 'cramps'),
        LogOption(l10n.logSympHeadache, 'headache'),
        LogOption(l10n.logSympBloating, 'bloating'),
        LogOption(l10n.logSympAcne, 'acne'),
      ];
}