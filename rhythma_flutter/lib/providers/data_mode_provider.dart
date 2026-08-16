import 'package:flutter/foundation.dart';
import '../config/app_config.dart';

/// Represents the current data source mode.
enum DataMode {
  /// Connected to the production backend.
  live,

  /// Connected to a local/development/staging backend.
  dev,
}

/// Single source of truth for the active data mode.
///
/// Detects the mode at construction by inspecting the compile-time API base
/// URL.  This provider never changes state at runtime — the mode is fixed
/// once the app starts.
class DataModeProvider extends ChangeNotifier {
  DataModeProvider() : _mode = _detectMode();

  static DataMode _detectMode() {
    const url = AppConfig.apiBaseUrl;
    if (url.contains('api.rhythma.app')) {
      return DataMode.live;
    }
    return DataMode.dev;
  }

  final DataMode _mode;

  DataMode get mode => _mode;

  /// Convenience getter for widget use.
  bool get isLive => _mode == DataMode.live;

  /// Convenience getter for widget use.
  bool get isDev => _mode == DataMode.dev;

  /// Human-readable label for display in the debug indicator.
  String get label {
    switch (_mode) {
      case DataMode.live:
        return 'Live Data';
      case DataMode.dev:
        return 'Dev Data';
    }
  }

  /// Compile-time API base URL, exposed so the indicator can show it.
  String get apiUrl => AppConfig.apiBaseUrl;
}
