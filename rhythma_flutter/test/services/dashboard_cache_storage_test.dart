import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/services/dashboard_cache.dart';
import 'package:rhythma/services/local_storage_service.dart';

/// The storage half of #510: the timestamp that was written and never read.
///
/// `dashboard_cache.dart` holds the policy and is tested without Hive.
/// This file covers the accessors — that the saved-at value comes back,
/// that `readCachedDashboard` applies the policy to it, and that logging
/// out has something to call.
void main() {
  late Directory tempDir;

  setUp(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    FlutterSecureStorage.setMockInitialValues({});
    tempDir = await Directory.systemTemp.createTemp('hive_dashboard_cache');
    Hive.init(tempDir.path);
    await LocalStorageService.init(testPath: tempDir.path);
    await LocalStorageService.setCurrentUserId('user-asha');
  });

  tearDown(() async {
    await Hive.close();
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  Map<String, dynamic> payload() => {
        'user': {'name': 'Asha'},
        'cycle': {'day': 12, 'total': 28, 'nextPeriodDays': 16},
        'insights': {'averageCycleLength': 28},
      };

  test('saving records when it was saved', () async {
    final before = DateTime.now();
    await LocalStorageService.saveCachedDashboard(payload());

    final savedAt = LocalStorageService.getCachedDashboardSavedAt();

    expect(savedAt, isNotNull);
    expect(savedAt!.isBefore(before.subtract(const Duration(seconds: 5))), isFalse);
  });

  test('there is no saved-at value before anything is saved', () {
    expect(LocalStorageService.getCachedDashboardSavedAt(), isNull);
    expect(LocalStorageService.getCachedDashboardAge(), isNull);
  });

  test('the age is measured against the supplied clock', () async {
    await LocalStorageService.saveCachedDashboard(payload());
    final savedAt = LocalStorageService.getCachedDashboardSavedAt()!;

    final age = LocalStorageService.getCachedDashboardAge(
      now: savedAt.add(const Duration(hours: 30)),
    );

    expect(age, const Duration(hours: 30));
  });

  test('a freshly saved dashboard reads back as fresh', () async {
    await LocalStorageService.saveCachedDashboard(payload());

    final entry = LocalStorageService.readCachedDashboard();

    expect(entry.status, DashboardCacheStatus.fresh);
    expect(entry.data!['cycle']['day'], 12);
    expect(entry.needsAgeNotice, isFalse);
  });

  test('a day-old dashboard reads back as stale, with its age', () async {
    await LocalStorageService.saveCachedDashboard(payload());
    final savedAt = LocalStorageService.getCachedDashboardSavedAt()!;

    final entry = LocalStorageService.readCachedDashboard(
      now: savedAt.add(const Duration(days: 1)),
    );

    expect(entry.status, DashboardCacheStatus.stale);
    expect(entry.needsAgeNotice, isTrue);
    expect(entry.hasUsableData, isTrue);
  });

  test('a three-week-old dashboard reads back with no data', () async {
    // What the Home screen used to render as today's cycle day.
    await LocalStorageService.saveCachedDashboard(payload());
    final savedAt = LocalStorageService.getCachedDashboardSavedAt()!;

    final entry = LocalStorageService.readCachedDashboard(
      now: savedAt.add(const Duration(days: 21)),
    );

    expect(entry.isExpired, isTrue);
    expect(entry.hasUsableData, isFalse);
    expect(entry.data, isNull);
  });

  test('clearing removes both the payload and the timestamp', () async {
    await LocalStorageService.saveCachedDashboard(payload());

    await LocalStorageService.clearCachedDashboard();

    expect(LocalStorageService.getCachedDashboard(), isNull);
    expect(LocalStorageService.getCachedDashboardSavedAt(), isNull);
    expect(
      LocalStorageService.readCachedDashboard().status,
      DashboardCacheStatus.absent,
    );
  });

  test('one account cannot read another account\'s saved dashboard', () async {
    await LocalStorageService.saveCachedDashboard(payload());

    await LocalStorageService.setCurrentUserId('user-begum');

    expect(LocalStorageService.getCachedDashboard(), isNull);
    expect(LocalStorageService.getCachedDashboardSavedAt(), isNull);
  });

  test('clearing one account leaves the other account\'s cache alone', () async {
    await LocalStorageService.saveCachedDashboard(payload());

    await LocalStorageService.setCurrentUserId('user-begum');
    await LocalStorageService.saveCachedDashboard(payload());
    await LocalStorageService.clearCachedDashboard();

    expect(LocalStorageService.getCachedDashboard(), isNull);

    await LocalStorageService.setCurrentUserId('user-asha');
    expect(LocalStorageService.getCachedDashboard(), isNotNull);
  });
}
