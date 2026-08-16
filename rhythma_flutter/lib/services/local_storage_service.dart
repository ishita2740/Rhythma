import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:hive_flutter/hive_flutter.dart';

/// Keys used in Hive boxes
class _Keys {
  static const cycleBox = 'cycle_logs';
  static const settingsBox = 'settings';
  static const userBox = 'user_profile';
  static const profile = 'profile';
  static const chatHistory = 'chat_history';
  static const emergencyContacts = 'emergency_contacts';
  static const onboardingCompleted = 'onboarding_completed';
  static const language = 'language';
  static const languageSelectionCompleted = 'language_selection_completed';
  static const cloudSync = 'cloud_sync';
  static const smsEnabled = 'sms_enabled';
  static const biometricEnabled = 'biometric_enabled';
  static const themeMode = 'theme_mode';
  static const primaryColor = 'primary_color';
  static const currentUserId = 'current_user_id';
  static const dashboardCache = 'dashboard_cache';
  static const dashboardCacheTimestamp = 'dashboard_cache_timestamp';
}

/// Manages all on-device storage via Hive.
class LocalStorageService {
  static bool _initialised = false;

  /// Call once at app startup (after WidgetsFlutterBinding.ensureInitialized)
  static Future<void> init({String? testPath}) async {
    if (_initialised) return;

    if (testPath != null) {
      Hive.init(testPath);
    } else {
      await Hive.initFlutter();
    }

    const secureStorage = FlutterSecureStorage();
    var encryptionKeyString = await secureStorage.read(key: 'hive_key');
    bool needsMigration = false;

    if (encryptionKeyString == null) {
      final key = Hive.generateSecureKey();
      encryptionKeyString = base64UrlEncode(key);
      await secureStorage.write(key: 'hive_key', value: encryptionKeyString);
      needsMigration = true; // Flag that existing data is unencrypted
    }

    final cipher = HiveAesCipher(base64Url.decode(encryptionKeyString));

    // 1. Handle migration for existing users for cycleBox
    if (needsMigration && await Hive.boxExists(_Keys.cycleBox)) {
      final oldBox = await Hive.openBox<Map>(_Keys.cycleBox);
      final oldData = oldBox.toMap();
      await oldBox.close();
      await Hive.deleteBoxFromDisk(_Keys.cycleBox); // Delete unencrypted file

      final newBox = await Hive.openBox<Map>(_Keys.cycleBox, encryptionCipher: cipher);
      await newBox.putAll(oldData); // Restore data securely
    } else {
      await Hive.openBox<Map>(_Keys.cycleBox, encryptionCipher: cipher);
    }

    // 2. Handle migration for existing users for userBox
    if (needsMigration && await Hive.boxExists(_Keys.userBox)) {
      final oldBox = await Hive.openBox<Map>(_Keys.userBox);
      final oldData = oldBox.toMap();
      await oldBox.close();
      await Hive.deleteBoxFromDisk(_Keys.userBox); // Delete unencrypted file

      final newBox = await Hive.openBox<Map>(_Keys.userBox, encryptionCipher: cipher);
      await newBox.putAll(oldData); // Restore data securely
    } else {
      await Hive.openBox<Map>(_Keys.userBox, encryptionCipher: cipher);
    }

    // 3. Open non-sensitive settings unencrypted
    await Hive.openBox<dynamic>(_Keys.settingsBox);

    _initialised = true;
  }

  // ── Per-account data scoping ──────────────────────────────────────────

  static const _kCurrentUserId = _Keys.currentUserId;

  static String? get currentUserId {
    return _settings.get(_kCurrentUserId) as String?;
  }

  static Future<void> setCurrentUserId(String? userId) async {
    if (userId == null) {
      await _settings.delete(_kCurrentUserId);
      return;
    }
    await _migrateLegacyDataIfNeeded(userId);
    await _settings.put(_kCurrentUserId, userId);
  }

  static String _scoped(String baseKey) {
    final uid = currentUserId;
    return uid == null ? baseKey : '$uid::$baseKey';
  }

  /// One-time migration: silently moves any pre-existing un-scoped entries
  /// into the first account that logs in after this update.
  static Future<void> _migrateLegacyDataIfNeeded(String uid) async {
    final scopedProfileKey = '$uid::${_Keys.profile}';
    if (_userBox.containsKey(_Keys.profile) &&
        !_userBox.containsKey(scopedProfileKey)) {
      final legacyProfile = _userBox.get(_Keys.profile);
      if (legacyProfile != null) {
        await _userBox.put(scopedProfileKey, legacyProfile);
      }
      await _userBox.delete(_Keys.profile);
    }

    const legacyChatKey = 'chat_history';
    final scopedChatKey = '$uid::chat_history';
    if (_settings.containsKey(legacyChatKey) &&
        !_settings.containsKey(scopedChatKey)) {
      await _settings.put(scopedChatKey, _settings.get(legacyChatKey));
      await _settings.delete(legacyChatKey);
    }

    final legacyCycleKeys =
        _cycleBox.keys.where((k) => !k.toString().contains('::')).toList();
    for (final key in legacyCycleKeys) {
      final legacyLog = _cycleBox.get(key);
      if (legacyLog != null) {
        await _cycleBox.put('$uid::$key', legacyLog);
      }
      await _cycleBox.delete(key);
    }
  }

  // ── Cycle Logs ──────────────────────────────────────────────────────────

  static Box<Map> get _cycleBox => Hive.box<Map>(_Keys.cycleBox);

  static Future<void> saveCycleLog(Map<String, dynamic> log) async {
    final key = log['start_date'] as String;
    await _cycleBox.put(_scoped(key), log);
  }

  static List<Map<String, dynamic>> getCycleLogs() {
    final uid = currentUserId;
    final prefix = uid == null ? null : '$uid::';
    return _cycleBox.keys
        .where((k) {
          final key = k.toString();
          return prefix != null ? key.startsWith(prefix) : !key.contains('::');
        })
        .map((k) => Map<String, dynamic>.from(_cycleBox.get(k) as Map))
        .toList()
      ..sort((a, b) =>
          (b['start_date'] as String).compareTo(a['start_date'] as String));
  }

  static List<Map<String, dynamic>> getRecentCycleLogs({int n = 6}) {
    return getCycleLogs().take(n).toList();
  }

  /// Removes a cycle log entry identified by its date key (YYYY-MM-DD).
  static Future<void> deleteCycleLog(String dateKey) async {
    await _cycleBox.delete(_scoped(dateKey));
  }

  // ── User Settings ──────────────────────────────────────────────────────

  static Box<dynamic> get _settings => Hive.box<dynamic>(_Keys.settingsBox);

  static String get preferredLanguage {
    return _settings.get(_Keys.language, defaultValue: 'en') as String;
  }

  static Future<void> setPreferredLanguage(String code) async {
    await _settings.put(_Keys.language, code);
  }

  static bool get languageSelectionCompleted {
    return _settings.get(_Keys.languageSelectionCompleted, defaultValue: false)
        as bool;
  }

  static Future<void> setLanguageSelectionCompleted(bool value) async {
    await _settings.put(_Keys.languageSelectionCompleted, value);
  }

  static bool get cloudSyncEnabled {
    return _settings.get(_Keys.cloudSync, defaultValue: false) as bool;
  }

  static Future<void> setCloudSync(bool enabled) async {
    await _settings.put(_Keys.cloudSync, enabled);
  }

  static bool get smsEnabled {
    return _settings.get(_Keys.smsEnabled, defaultValue: false) as bool;
  }

  static Future<void> setSmsEnabled(bool enabled) async {
    await _settings.put(_Keys.smsEnabled, enabled);
  }

  static bool get biometricEnabled {
    return _settings.get(_Keys.biometricEnabled, defaultValue: false) as bool;
  }

  static Future<void> setBiometricEnabled(bool enabled) async {
    await _settings.put(_Keys.biometricEnabled, enabled);
  }

  static String? getThemeMode() {
    return _settings.get(_Keys.themeMode) as String?;
  }

  static Future<void> setThemeMode(String mode) async {
    await _settings.put(_Keys.themeMode, mode);
  }

  static int? getPrimaryColor() {
    return _settings.get(_Keys.primaryColor) as int?;
  }

  static Future<void> setPrimaryColor(int colorValue) async {
    await _settings.put(_Keys.primaryColor, colorValue);
  }

  // ── Onboarding ──────────────────────────────────────────────────────────

  /// Onboarding completion is scoped per user, so each account has its own state.
  static bool get onboardingCompleted {
    return _settings.get(_scoped(_Keys.onboardingCompleted), defaultValue: false)
        as bool;
  }

  static Future<void> setOnboardingCompleted(bool value) async {
    await _settings.put(_scoped(_Keys.onboardingCompleted), value);
  }

  // ── User Profile ────────────────────────────────────────────────────────

  static Box<Map> get _userBox => Hive.box<Map>(_Keys.userBox);

  static Map<String, dynamic>? getProfile() {
    final raw = _userBox.get(_scoped(_Keys.profile));
    return raw != null ? Map<String, dynamic>.from(raw) : null;
  }

  static Future<void> saveProfile(Map<String, dynamic> profile) async {
    await _userBox.put(_scoped(_Keys.profile), profile);
    final lang = profile['language'] as String?;
    if (lang != null) await setPreferredLanguage(lang);
  }

  static Future<void> mergeProfile(Map<String, dynamic> updates) async {
    final existing = getProfile() ?? {};
    final merged = {...existing, ...updates};
    await saveProfile(merged);
  }

  // ── Quick Log Field ────────────────────────────────────────────────────

  static Future<void> saveQuickLogField(DateTime date, String field, dynamic value) async {
    final key = _scoped(_dateKey(date));
    final existing = _cycleBox.get(key);
    final data = existing != null
        ? Map<String, dynamic>.from(existing)
        : <String, dynamic>{'start_date': _dateKey(date)};
    data[field] = value;
    await _cycleBox.put(key, data);
  }

  static Map<String, dynamic>? getCycleLogForDate(DateTime date) {
    final raw = _cycleBox.get(_scoped(_dateKey(date)));
    return raw != null ? Map<String, dynamic>.from(raw) : null;
  }

  static String _dateKey(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';

  // ── Emergency Contacts ─────────────────────────────────────────────────

  static List<Map<String, String>> getEmergencyContacts() {
    final raw = _settings.get(_scoped(_Keys.emergencyContacts));
    if (raw != null) {
      return List<Map<String, String>>.from(
        (raw as List).map((e) => Map<String, String>.from(e as Map)),
      );
    }
    return [];
  }

  static Future<void> saveEmergencyContacts(List<Map<String, String>> contacts) async {
    await _settings.put(_scoped(_Keys.emergencyContacts), contacts);
  }

  // ── Assistant Chat History ─────────────────────────────────────────────

  static List<Map<String, String>> getChatHistory() {
    final raw = _settings.get(_scoped(_Keys.chatHistory));
    if (raw != null) {
      return List<Map<String, String>>.from(
        (raw as List).map((e) => Map<String, String>.from(e as Map)),
      );
    }
    return [];
  }

  static Future<void> saveChatHistory(List<Map<String, String>> history) =>
      _settings.put(_scoped(_Keys.chatHistory), history);

  static Future<void> clearChatHistory() =>
      _settings.delete(_scoped(_Keys.chatHistory));

  // ── Nudge Preferences ───────────────────────────────────────────────

  static bool getNudgeDismissed(String key) {
    return _settings.get(_scoped('nudge_$key'), defaultValue: false) as bool;
  }

  static Future<void> setNudgeDismissed(String key, bool value) async {
    await _settings.put(_scoped('nudge_$key'), value);
  }

  // ── Notification Preferences ─────────────────────────────────────────

  static bool get periodPredictionReminders {
    return _settings.get(_scoped('period_prediction_reminders'), defaultValue: true)
        as bool;
  }

  static Future<void> setPeriodPredictionReminders(bool value) async {
    await _settings.put(_scoped('period_prediction_reminders'), value);
  }

  static bool get loggingReminders {
    return _settings.get(_scoped('logging_reminders'), defaultValue: true)
        as bool;
  }

  static Future<void> setLoggingReminders(bool value) async {
    await _settings.put(_scoped('logging_reminders'), value);
  }

  // ── Dashboard Cache ────────────────────────────────────────────────────

  static Map<String, dynamic>? getCachedDashboard() {
    final raw = _settings.get(_scoped(_Keys.dashboardCache));
    return raw != null ? Map<String, dynamic>.from(raw as Map) : null;
  }

  static Future<void> saveCachedDashboard(Map<String, dynamic> data) async {
    await _settings.put(_scoped(_Keys.dashboardCache), data);
    await _settings.put(
        _scoped(_Keys.dashboardCacheTimestamp), DateTime.now().toIso8601String());
  }

  // ── Clear all data ─────────────────────────────────────────────────────

  static Future<void> deleteCurrentUserData() async {
    final uid = currentUserId;
    if (uid == null) return;
    final prefix = '$uid::';

    // Remove cycle logs for this user
    final cycleKeys = _cycleBox.keys.where((k) => k.toString().startsWith(prefix)).toList();
    for (final k in cycleKeys) {
      await _cycleBox.delete(k);
    }

    // Remove user profile for this user
    final userKeys = _userBox.keys.where((k) => k.toString().startsWith(prefix)).toList();
    for (final k in userKeys) {
      await _userBox.delete(k);
    }

    // Remove settings for this user
    final settingsKeys = _settings.keys.where((k) => k.toString().startsWith(prefix)).toList();
    for (final k in settingsKeys) {
      await _settings.delete(k);
    }
    
    // Also remove unscoped legacy profile & dashboard cache keys
    await _settings.delete(_Keys.profile);
    await _settings.delete(_Keys.dashboardCache);

    // Also remove the current user id marker
    await _settings.delete(_kCurrentUserId);
  }

  static Future<void> clearAll() async {
    await _cycleBox.clear();
    await _settings.clear();
    await _userBox.clear();
  }
}