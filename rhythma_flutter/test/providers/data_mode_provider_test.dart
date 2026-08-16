import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/config/app_config.dart';
import 'package:rhythma/providers/data_mode_provider.dart';

void main() {
  group('DataModeProvider', () {
    test('detects live mode for production API URL', () {
      // The default AppConfig.apiBaseUrl is https://api.rhythma.app/api/v1
      expect(AppConfig.apiBaseUrl.startsWith('https://api.rhythma.app'), isTrue);

      final provider = DataModeProvider();
      expect(provider.isLive, isTrue);
      expect(provider.isDev, isFalse);
      expect(provider.mode, DataMode.live);
    });

    test('returns correct label for live mode', () {
      final provider = DataModeProvider();
      expect(provider.label, 'Live Data');
    });

    test('exposes apiUrl from AppConfig', () {
      final provider = DataModeProvider();
      expect(provider.apiUrl, AppConfig.apiBaseUrl);
    });
  });
}
