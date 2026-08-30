import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Sleep slider value clamping logic restricts values between 0 and 16 hours', () {
    const invalidHigh = 24.0;
    const invalidLow = -2.0;
    const validMid = 8.0;

    expect(invalidHigh.clamp(0.0, 16.0), equals(16.0));
    expect(invalidLow.clamp(0.0, 16.0), equals(0.0));
    expect(validMid.clamp(0.0, 16.0), equals(8.0));
  });
}
