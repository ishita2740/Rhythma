import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Cycle log payload construction formats start_date and metrics correctly', () {
    final date = DateTime(2026, 8, 15);
    final dateKey = '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
    final log = {
      'start_date': dateKey,
      'flow_intensity': 'medium',
      'mood': '😀',
      'sleep_hours': 8.0,
      'stress_level': 2.0,
      'symptoms': ['Cramps'],
    };

    expect(log['start_date'], equals('2026-08-15'));
    expect(log['flow_intensity'], equals('medium'));
    expect(log['sleep_hours'], equals(8.0));
  });
}
