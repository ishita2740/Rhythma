import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/services/local_storage_service.dart';

/// Initializes Hive with a temporary directory for testing and opens the
/// boxes that [LocalStorageService] depends on.
///
/// Call this in the `setUp` of any test that calls [LocalStorageService]
/// methods.  Call [tearDownLocalStorage] in `tearDown` to close Hive and
/// remove the temporary directory.
Future<Directory> setUpLocalStorage() async {
  final tempDir = await Directory.systemTemp.createTemp('hive_test_dir');
  Hive.init(tempDir.path);

  await Hive.openBox<Map>('cycle_logs');
  await Hive.openBox<Map>('user_profile');
  await Hive.openBox<dynamic>('settings');

  FlutterSecureStorage.setMockInitialValues({});

  return tempDir;
}

/// Closes Hive and removes [tempDir] from disk.
Future<void> tearDownLocalStorage(Directory tempDir) async {
  await Hive.close();
  if (tempDir.existsSync()) {
    tempDir.deleteSync(recursive: true);
  }
}

/// Seeds a profile into the user_profile Hive box for [userId].
Future<void> seedProfile(String userId, Map<String, dynamic> profile) async {
  final box = Hive.box<Map>('user_profile');
  await box.put('$userId::profile', profile);
}

/// Seeds a list of cycle logs into the cycle_logs Hive box for [userId].
Future<void> seedCycleLogs(
    String userId, List<Map<String, dynamic>> logs) async {
  final box = Hive.box<Map>('cycle_logs');
  for (final log in logs) {
    final key = log['start_date'] as String;
    await box.put('$userId::$key', log);
  }
}

/// Seeds the onboarding-completed flag for [userId].
Future<void> seedOnboardingCompleted(String userId, bool value) async {
  final box = Hive.box<dynamic>('settings');
  await box.put('$userId::onboarding_completed', value);
}

/// Seeds emergency contacts for [userId].
Future<void> seedEmergencyContacts(
    String userId, List<Map<String, String>> contacts) async {
  final box = Hive.box<dynamic>('settings');
  await box.put('$userId::emergency_contacts', contacts);
}

/// Seeds the current user ID in settings.
Future<void> seedCurrentUserId(String userId) async {
  final box = Hive.box<dynamic>('settings');
  await box.put('current_user_id', userId);
}
