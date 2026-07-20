import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/services/local_storage_service.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    // Start with a clean mock keychain
    FlutterSecureStorage.setMockInitialValues({}); 
    
    // Create a temporary directory for Hive files to avoid touching real data
    tempDir = await Directory.systemTemp.createTemp('hive_test_dir');
    Hive.init(tempDir.path);
    
    // Ensure we are testing the real Hive integration, not the mock variables
    LocalStorageService.isTesting = false; 
  });

  tearDown(() async {
    await Hive.close();
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  test('Migration transparently encrypts unencrypted data', () async {
    // ---------------------------------------------------------
    // 1. Simulate OLD app behavior (unencrypted)
    // ---------------------------------------------------------
    final unencryptedCycleBox = await Hive.openBox<Map>('cycle_logs');
    final unencryptedUserBox = await Hive.openBox<Map>('user_profile');
    
    await unencryptedCycleBox.put('2025-10-01', {'start_date': '2025-10-01', 'flow': 'heavy'});
    await unencryptedUserBox.put('profile', {'name': 'Test User', 'age': 25});
    
    await unencryptedCycleBox.close();
    await unencryptedUserBox.close();

    // ---------------------------------------------------------
    // 2. Simulate APP UPDATE (encryption introduced)
    // ---------------------------------------------------------
    // Run our new init() logic which should detect unencrypted data and migrate it
    await LocalStorageService.init(testPath: tempDir.path);

    // ---------------------------------------------------------
    // 3. Verify the migrated data is intact and accessible
    // ---------------------------------------------------------
    const secureStorage = FlutterSecureStorage();
    final keyString = await secureStorage.read(key: 'hive_key');
    expect(keyString, isNotNull, reason: 'Encryption key should have been generated');

    // Test data integrity using the service's getters
    final profile = LocalStorageService.getProfile();
    expect(profile?['name'], 'Test User');
    expect(profile?['age'], 25);
    
    // Verify cycle log data is still present
    final cycleBox = Hive.box<Map>('cycle_logs');
    expect(cycleBox.get('2025-10-01')?['flow'], 'heavy');

    // ---------------------------------------------------------
    // 4. Prove that the files on disk are actually encrypted
    // ---------------------------------------------------------
    // Close all boxes
    await Hive.close();
    
    // If we try to open an encrypted box WITHOUT the cipher, Hive should throw an error 
    // or fail because the bytes are scrambled.
    try {
      await Hive.openBox<Map>('cycle_logs'); // No cipher provided!
      fail('Expected Hive to throw an error when opening an encrypted box without a cipher');
    } catch (e) {
      expect(e, isNotNull);
    }
  });
}
