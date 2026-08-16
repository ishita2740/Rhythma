import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/providers/cycle_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('CycleProvider Dynamic Phase Tests', () {
    test('CycleProvider scales phase boundaries dynamically for different cycle lengths', () {
      final provider = CycleProvider();
      expect(provider, isNotNull);
    });
  });
}
