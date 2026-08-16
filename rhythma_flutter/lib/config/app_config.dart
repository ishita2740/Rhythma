import 'package:flutter/foundation.dart';

class AppConfig {
  // Usage:
  //   flutter run --dart-define=API_BASE_URL=https://api.rhythma.app/api/v1
  //   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1  (local dev)
  //
  // Default is HTTPS. For local development against a local backend, pass
  // the flag above with an http:// URL — the debug manifest on Android
  // permits cleartext traffic so this still works.
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://api.rhythma.app/api/v1',
  );
}