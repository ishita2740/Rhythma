import 'package:flutter/foundation.dart';

class AppConfig {
  // Usage:
  // flutter run --dart-define=API_BASE_URL=http://your-ip:8000/api/v1
  // Default is Android emulator (10.0.2.2) or Web (localhost)
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue:
        kIsWeb ? 'http://localhost:8000/api/v1' : 'http://10.0.2.2:8000/api/v1',
  );
}
