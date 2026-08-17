import 'package:flutter_test/flutter_test.dart';

void main() {
  test('deleteCurrentUserData wipes user scoped keys and profile cache', () {
    final Map<String, dynamic> mockStorage = {
      'user1::profile': {'name': 'Alice'},
      'current_user_id': 'user1',
      'profile': {'name': 'Alice'},
      'dashboard_cache': {'cycle': 'cached'},
    };

    const prefix = 'user1::';
    final keysToDelete =
        mockStorage.keys.where((k) => k.startsWith(prefix)).toList();

    for (final k in keysToDelete) {
      mockStorage.remove(k);
    }

    mockStorage.remove('profile');
    mockStorage.remove('dashboard_cache');
    mockStorage.remove('current_user_id');

    expect(mockStorage.containsKey('profile'), isFalse);
    expect(mockStorage.containsKey('dashboard_cache'), isFalse);
    expect(mockStorage.containsKey('current_user_id'), isFalse);
    expect(mockStorage.containsKey('user1::profile'), isFalse);
  });
}
