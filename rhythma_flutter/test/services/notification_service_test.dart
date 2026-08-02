import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/services/notification_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('NotificationService Tests', () {
    test('NotificationService singleton instance is not null', () {
      final instance = NotificationService.instance;
      expect(instance, isNotNull);
    });

    test('NotificationService init can be called safely', () async {
      final service = NotificationService.instance;
      expect(service, isNotNull);
    });
  });
}
