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
  static const cloudSync = 'cloud_sync';
  static const smsEnabled = 'sms_enabled';
  static const themeMode = 'theme_mode';
  static const primaryColor = 'primary_color';
  static const currentUserId = 'current_user_id';
}

/// Manages all on-device storage via Hive.
class LocalStorageService {
  static bool _initialised = false;

  // Test mocks to bypass Hive during unit/widget tests
  static bool isTesting = false;
  static Map<String, dynamic>? mockProfile;
  static List<Map<String, String>> mockEmergencyContacts = [];
  static bool mockOnboardingCompleted = false;
  static List<Map<String, dynamic>> mockCycleLogs = [];
  static String? mockCurrentUserId;

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
    if (isTesting) return mockCurrentUserId;
    return _settings.get(_kCurrentUserId) as String?;
  }

  static Future<void> setCurrentUserId(String? userId) async {
    if (isTesting) {
      mockCurrentUserId = userId;
      return;
    }
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
    if (isTesting) {
      final index =
          mockCycleLogs.indexWhere((l) => l['start_date'] == log['start_date']);
      if (index != -1) {
        mockCycleLogs[index] = log;
      } else {
        mockCycleLogs.add(log);
      }
      return;
    }
    final key = log['start_date'] as String;
    await _cycleBox.put(_scoped(key), log);
  }

  static List<Map<String, dynamic>> getCycleLogs() {
    if (isTesting) {
      return List<Map<String, dynamic>>.from(mockCycleLogs)
        ..sort((a, b) =>
            (b['start_date'] as String).compareTo(a['start_date'] as String));
    }
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
    if (isTesting) return [];
    return getCycleLogs().take(n).toList();
  }

  // ── User Settings ──────────────────────────────────────────────────────

  static Box<dynamic> get _settings => Hive.box<dynamic>(_Keys.settingsBox);

  static String get preferredLanguage {
    if (isTesting) return 'en';
    return _settings.get(_Keys.language, defaultValue: 'en') as String;
  }

  static Future<void> setPreferredLanguage(String code) async {
    if (isTesting) return;
    await _settings.put(_Keys.language, code);
  }

  static bool get cloudSyncEnabled {
    if (isTesting) return false;
    return _settings.get(_Keys.cloudSync, defaultValue: false) as bool;
  }

  static Future<void> setCloudSync(bool enabled) async {
    if (isTesting) return;
    await _settings.put(_Keys.cloudSync, enabled);
  }

  static bool get smsEnabled {
    if (isTesting) return false;
    return _settings.get(_Keys.smsEnabled, defaultValue: false) as bool;
  }

  static Future<void> setSmsEnabled(bool enabled) async {
    if (isTesting) return;
    await _settings.put(_Keys.smsEnabled, enabled);
  }

  static String? getThemeMode() {
    if (isTesting) return null;
    return _settings.get(_Keys.themeMode) as String?;
  }

  static Future<void> setThemeMode(String mode) async {
    if (isTesting) return;
    await _settings.put(_Keys.themeMode, mode);
  }

  static int? getPrimaryColor() {
    if (isTesting) return null;
    return _settings.get(_Keys.primaryColor) as int?;
  }

  static Future<void> setPrimaryColor(int colorValue) async {
    if (isTesting) return;
    await _settings.put(_Keys.primaryColor, colorValue);
  }

  // ── Onboarding ──────────────────────────────────────────────────────────

  /// Onboarding completion is scoped per user, so each account has its own state.
  static bool get onboardingCompleted {
    if (isTesting) return mockOnboardingCompleted;
    return _settings.get(_scoped(_Keys.onboardingCompleted), defaultValue: false)
        as bool;
  }

  static Future<void> setOnboardingCompleted(bool value) async {
    if (isTesting) {
      mockOnboardingCompleted = value;
      return;
    }
    await _settings.put(_scoped(_Keys.onboardingCompleted), value);
  }

  // ── User Profile ────────────────────────────────────────────────────────

  static Box<Map> get _userBox => Hive.box<Map>(_Keys.userBox);

  static Map<String, dynamic>? getProfile() {
    if (isTesting) return mockProfile;
    final raw = _userBox.get(_scoped(_Keys.profile));
    return raw != null ? Map<String, dynamic>.from(raw) : null;
  }

  static Future<void> saveProfile(Map<String, dynamic> profile) async {
    if (isTesting) {
      mockProfile = profile;
      return;
    }
    await _userBox.put(_scoped(_Keys.profile), profile);
    final lang = profile['language'] as String?;
    if (lang != null) await setPreferredLanguage(lang);
  }

  static Future<void> mergeProfile(Map<String, dynamic> updates) async {
    final existing = getProfile() ?? {};
    final merged = {...existing, ...updates};
    await saveProfile(merged);
    if (isTesting) mockProfile = merged;
  }

  // ── Quick Log Field ────────────────────────────────────────────────────

  static Future<void> saveQuickLogField(DateTime date, String field, dynamic value) async {
    if (isTesting) {
      final key = _dateKey(date);
      final index = mockCycleLogs.indexWhere((l) => l['start_date'] == key);
      if (index != -1) {
        mockCycleLogs[index] = {...mockCycleLogs[index], field: value};
      } else {
        mockCycleLogs.add({'start_date': key, field: value});
      }
      return;
    }
    final key = _scoped(_dateKey(date));
    final existing = _cycleBox.get(key);
    final data = existing != null
        ? Map<String, dynamic>.from(existing)
        : <String, dynamic>{'start_date': _dateKey(date)};
    data[field] = value;
    await _cycleBox.put(key, data);
  }

  static Map<String, dynamic>? getCycleLogForDate(DateTime date) {
    if (isTesting) {
      final key = _dateKey(date);
      final match = mockCycleLogs.where((l) => l['start_date'] == key);
      return match.isEmpty ? null : Map<String, dynamic>.from(match.first);
    }
    final raw = _cycleBox.get(_scoped(_dateKey(date)));
    return raw != null ? Map<String, dynamic>.from(raw) : null;
  }

  static String _dateKey(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';

  // ── Emergency Contacts ─────────────────────────────────────────────────

  static List<Map<String, String>> getEmergencyContacts() {
    if (isTesting) return mockEmergencyContacts;
    final raw = _settings.get(_scoped(_Keys.emergencyContacts));
    if (raw != null) {
      return List<Map<String, String>>.from(
        (raw as List).map((e) => Map<String, String>.from(e as Map)),
      );
    }
    return [];
  }

  static Future<void> saveEmergencyContacts(List<Map<String, String>> contacts) async {
    if (isTesting) {
      mockEmergencyContacts = contacts;
      return;
    }
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

  // ── Clear all data ─────────────────────────────────────────────────────

  static Future<void> clearAll() async {
    if (isTesting) {
      mockProfile = null;
      mockEmergencyContacts = [];
      mockOnboardingCompleted = false;
      return;
    }
    await _cycleBox.clear();
    await _settings.clear();
    await _userBox.clear();
  }
}