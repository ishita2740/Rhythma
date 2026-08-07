import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/services/export_service.dart';

import '../test_helpers/local_storage_fixture.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('ExportService Tests', () {
    setUp(() async {
      await setUpLocalStorage();
    });

    test('buildExportJson creates valid JSON export string', () {
      final jsonString = ExportService.buildExportJson();
      expect(jsonString, isNotEmpty);
      expect(jsonString, contains('export_date'));
      expect(jsonString, contains('profile'));
    });
  });
}
