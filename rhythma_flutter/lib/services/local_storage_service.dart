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

  // ── Per-account settings ─────────────────────────────────────────────
  //
  // Cycle logs, the profile, chat history and `onboardingCompleted` all go
  // through `_scoped()`. Six settings did not, and were read straight off
  // the bare key — so on a shared phone they were not "kept for the
  // previous account", they were inherited by the next one (#521).
  //
  // They split into two groups, and the difference matters more than the
  // de-duplication does.

  /// Settings that decide whether data leaves the device, or whether the
  /// app unlocks at all.
  ///
  /// `cloud_sync` is the one that makes this a privacy bug rather than a
  /// cosmetic one: `firestore_service` checks it before every write, so a
  /// previous user leaving it on means the *next* account's cycle logs and
  /// profile are uploaded to Firestore from her first entry, without her
  /// ever being asked.
  ///
  /// These never fall back to a device-level value. An account that has
  /// not answered the question is treated as not having consented, which
  /// is the only safe reading of silence.
  static const List<String> _consentKeys = <String>[
    _Keys.cloudSync,
    _Keys.smsEnabled,
    _Keys.biometricEnabled,
  ];

  /// Settings that are a preference about this phone rather than a
  /// decision about an account's data.
  ///
  /// These *do* fall back to the device-level value, because the language
  /// picker runs before sign-in — `language_selection_screen` is reached
  /// with no account to attribute the choice to — and a theme chosen on
  /// the login screen should survive reaching the home screen. A
  /// signed-in user's own choice still wins whenever she has made one.
  static const List<String> _preferenceKeys = <String>[
    _Keys.language,
    _Keys.themeMode,
    _Keys.primaryColor,
  ];

  /// This account's value for [baseKey], or `null` if she has none.
  ///
  /// A preference falls back to the device-level value; a consent flag
  /// does not. Which it is comes from [_preferenceKeys] rather than from
  /// an argument, so the classification is made once per setting instead
  /// of being restated — correctly or otherwise — at each call site.
  ///
  /// With no account signed in, `_scoped` returns the bare key, so this
  /// reads the device-level value, which is what the pre-login screens
  /// want.
  static T? _scopedSetting<T>(String baseKey) {
    final scopedKey = _scoped(baseKey);
    if (_settings.containsKey(scopedKey)) {
      return _settings.get(scopedKey) as T?;
    }
    if (_preferenceKeys.contains(baseKey) && _settings.containsKey(baseKey)) {
      return _settings.get(baseKey) as T?;
    }
    return null;
  }

  /// Writes [value] for this account.
  ///
  /// A preference is also mirrored to the device level, so the pre-login
  /// screens follow the most recent choice instead of reverting to the
  /// default on the login screen.
  ///
  /// A consent flag is never mirrored. Mirroring one would put it back
  /// exactly where the next account would find it, which is the bug.
  static Future<void> _putScopedSetting(String baseKey, Object? value) async {
    final scopedKey = _scoped(baseKey);
    await _settings.put(scopedKey, value);
    if (_preferenceKeys.contains(baseKey) && scopedKey != baseKey) {
      await _settings.put(baseKey, value);
    }
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

    // Consent flags written before they were namespaced belong to whoever
    // was using this phone, which is the account signing in now — the
    // first to do so after the upgrade. Adopt them, so a user who had
    // cloud sync or the biometric lock switched on does not silently lose
    // it.
    //
    // Then delete the device-level copy unconditionally, which is what
    // stops a *second* account inheriting the first one's answer: after
    // this runs there is no bare `cloud_sync` key left for it to find. The
    // delete is outside the adoption guard on purpose — an account that
    // already has its own value must still clear the shared one.
    for (final baseKey in _consentKeys) {
      final scopedKey = '$uid::$baseKey';
      if (_settings.containsKey(baseKey) && !_settings.containsKey(scopedKey)) {
        await _settings.put(scopedKey, _settings.get(baseKey));
      }
      await _settings.delete(baseKey);
    }

    // Preferences are deliberately *not* adopted here. They keep their
    // device-level value and `_scopedSetting` reads it back through
    // `_preferenceKeys`, so the pre-login language and theme keep working;
    // a scoped copy appears only once this account chooses for herself.
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
    return _scopedSetting<String>(_Keys.language) ?? 'en';
  }

  static Future<void> setPreferredLanguage(String code) async {
    await _putScopedSetting(_Keys.language, code);
  }

  static bool get languageSelectionCompleted {
    return _settings.get(_Keys.languageSelectionCompleted, defaultValue: false)
        as bool;
  }

  static Future<void> setLanguageSelectionCompleted(bool value) async {
    await _settings.put(_Keys.languageSelectionCompleted, value);
  }

  /// Whether this account has agreed to her data being synced to
  /// Firestore. Defaults to false with no device fallback — see
  /// [_consentKeys].
  static bool get cloudSyncEnabled {
    return _scopedSetting<bool>(_Keys.cloudSync) ?? false;
  }

  static Future<void> setCloudSync(bool enabled) async {
    await _putScopedSetting(_Keys.cloudSync, enabled);
  }

  static bool get smsEnabled {
    return _scopedSetting<bool>(_Keys.smsEnabled) ?? false;
  }

  static Future<void> setSmsEnabled(bool enabled) async {
    await _putScopedSetting(_Keys.smsEnabled, enabled);
  }

  static bool get biometricEnabled {
    return _scopedSetting<bool>(_Keys.biometricEnabled) ?? false;
  }

  static Future<void> setBiometricEnabled(bool enabled) async {
    await _putScopedSetting(_Keys.biometricEnabled, enabled);
  }

  static String? getThemeMode() {
    return _scopedSetting<String>(_Keys.themeMode);
  }

  static Future<void> setThemeMode(String mode) async {
    await _putScopedSetting(_Keys.themeMode, mode);
  }

  static int? getPrimaryColor() {
    return _scopedSetting<int>(_Keys.primaryColor);
  }

  static Future<void> setPrimaryColor(int colorValue) async {
    await _putScopedSetting(_Keys.primaryColor, colorValue);
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

    // And the device-level consent flags, for the case where this account
    // never went through `_migrateLegacyDataIfNeeded` — deleting an
    // account must not leave its cloud-sync or biometric answer sitting
    // where the next person to use the phone would inherit it (#521).
    for (final baseKey in _consentKeys) {
      await _settings.delete(baseKey);
    }

    // Also remove the current user id marker
    await _settings.delete(_kCurrentUserId);
  }

  static Future<void> clearAll() async {
    await _cycleBox.clear();
    await _settings.clear();
    await _userBox.clear();
  }
}