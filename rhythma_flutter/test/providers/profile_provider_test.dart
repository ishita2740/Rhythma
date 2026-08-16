import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/providers/profile_provider.dart';
import 'package:rhythma/services/local_storage_service.dart';

import '../test_helpers/local_storage_fixture.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('test-user');
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  test('loads the profile from local storage on construction', () async {
    await seedProfile('test-user', {'name': 'Aarya', 'age': 30});

    final provider = ProfileProvider();

    expect(provider.profile['name'], 'Aarya');
    expect(provider.profile['age'], 30);
  });

  test('starts with an empty profile when nothing is saved', () async {
    final provider = ProfileProvider();

    expect(provider.profile, isEmpty);
  });

  test('saveProfile persists and notifies listeners', () async {
    final provider = ProfileProvider();
    var notifications = 0;
    provider.addListener(() => notifications++);

    await provider.saveProfile({'name': 'Mira', 'age': 27});

    expect(notifications, greaterThan(0));
    expect(provider.profile['name'], 'Mira');
    expect(LocalStorageService.getProfile()?['name'], 'Mira');
  });

  test('mergeProfile merges updates into the existing profile', () async {
    await seedProfile('test-user', {'name': 'Aarya', 'cycle_length': 28});

    final provider = ProfileProvider();
    await provider.mergeProfile({'age': 30});

    expect(provider.profile['name'], 'Aarya');
    expect(provider.profile['age'], 30);
    expect(provider.profile['cycle_length'], 28);
    expect(LocalStorageService.getProfile()?['age'], 30);
  });

  test('mergeProfileWithSync persists locally and returns null even when the '
      'backend sync fails', () async {
    final provider = ProfileProvider();

    final result = await provider.mergeProfileWithSync({'name': 'Sync User'});

    expect(result, isNull);
    expect(provider.profile['name'], 'Sync User');
    expect(LocalStorageService.getProfile()?['name'], 'Sync User');
  });

  test('mergeProfileWithSync still returns null with cloud sync enabled',
      () async {
    await LocalStorageService.setCloudSync(true);

    final provider = ProfileProvider();

    final result = await provider.mergeProfileWithSync({'name': 'Cloud User'});

    expect(result, isNull);
    expect(provider.profile['name'], 'Cloud User');
  });

  test('reloadProfile picks up externally saved profile changes', () async {
    final provider = ProfileProvider();
    await provider.saveProfile({'name': 'First'});

    await seedProfile('test-user', {'name': 'External'});
    provider.reloadProfile();

    expect(provider.profile['name'], 'External');
  });
}
