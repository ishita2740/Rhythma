import 'package:flutter_test/flutter_test.dart';

void main() {
  test('notification ID is normalized to a valid 32-bit signed integer', () {
    const maxId = 0x7FFFFFFF;

    final ids = [
      -1,
      1,
      2147483648,
      1723588234567,
      -1723588234567,
    ];

    for (final id in ids) {
      final normalized = id.abs() % maxId;

      expect(normalized, greaterThanOrEqualTo(0));
      expect(normalized, lessThan(maxId));
    }
  });
}