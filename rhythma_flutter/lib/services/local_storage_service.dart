import 'package:hive_flutter/hive_flutter.dart';

/// Keys used in Hive boxes
class _Keys {
  static const cycleBox = 'cycle_logs';
  static const settingsBox = 'settings';
  static const userBox = 'user_profile';
}

/// Manages all on-device storage via Hive.
/// All health data is stored locally first and synced to Firestore
/// only when the user explicitly enables cloud sync.
class LocalStorageService {
  static bool _initialised = false;

  /// Call once at app startup (after WidgetsFlutterBinding.ensureInitialized)
  static Future<void> init() async {
    if (_initialised) return;
    await Hive.initFlutter();
    await Hive.openBox<Map>(_Keys.cycleBox);
    await Hive.openBox<dynamic>(_Keys.settingsBox);
    await Hive.openBox<Map>(_Keys.userBox);
    _initialised = true;
  }

  // ── Cycle Logs ────────────────────────────────────────────────────────────

  static Box<Map> get _cycleBox => Hive.box<Map>(_Keys.cycleBox);

  /// Save a cycle log entry. Key = ISO date string of start_date.
  static Future<void> saveCycleLog(Map<String, dynamic> log) async {
    final key = log['start_date'] as String;
    await _cycleBox.put(key, log);
  }

  /// Returns all cycle logs sorted by date (most recent first).
  static List<Map<String, dynamic>> getCycleLogs() {
    return _cycleBox.values
        .map((e) => Map<String, dynamic>.from(e))
        .toList()
      ..sort((a, b) =>
          (b['start_date'] as String).compareTo(a['start_date'] as String));
  }

  /// Returns the last [n] cycle logs.
  static List<Map<String, dynamic>> getRecentCycleLogs({int n = 6}) {
    return getCycleLogs().take(n).toList();
  }

  // ── User Settings ─────────────────────────────────────────────────────────

  static Box<dynamic> get _settings => Hive.box<dynamic>(_Keys.settingsBox);

  static String get preferredLanguage =>
      _settings.get('language', defaultValue: 'en') as String;

  static Future<void> setPreferredLanguage(String code) =>
      _settings.put('language', code);

  static bool get cloudSyncEnabled =>
      _settings.get('cloud_sync', defaultValue: false) as bool;

  static Future<void> setCloudSync(bool enabled) =>
      _settings.put('cloud_sync', enabled);

  static bool get smsEnabled =>
      _settings.get('sms_enabled', defaultValue: false) as bool;

  static Future<void> setSmsEnabled(bool enabled) =>
      _settings.put('sms_enabled', enabled);

  // ── User Profile ──────────────────────────────────────────────────────────

  static Box<Map> get _userBox => Hive.box<Map>(_Keys.userBox);

  static Map<String, dynamic>? getProfile() {
    final raw = _userBox.get('profile');
    return raw != null ? Map<String, dynamic>.from(raw) : null;
  }

  static Future<void> saveProfile(Map<String, dynamic> profile) =>
      _userBox.put('profile', profile);

  // ── Clear all data ────────────────────────────────────────────────────────

  static Future<void> clearAll() async {
    await _cycleBox.clear();
    await _settings.clear();
    await _userBox.clear();
  }
}
