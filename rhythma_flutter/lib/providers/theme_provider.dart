import 'package:flutter/material.dart';
import '../config/theme.dart';
import '../services/local_storage_service.dart';

class ThemeProvider extends ChangeNotifier {
  Color _primaryColor = const Color(0xFF9B72CF);
  bool _isDarkMode = false;

  Color get primaryColor => _primaryColor;
  bool get isDarkMode => _isDarkMode;
  ThemeMode get themeMode => _isDarkMode ? ThemeMode.dark : ThemeMode.light;

  ThemeProvider() {
    _loadTheme();
  }

  ThemeData? get theme => null;

  Future<void> _loadTheme() async {
    // Load Dark Mode
    String? modeStr = LocalStorageService.getThemeMode();
    if (modeStr != null) {
      _isDarkMode = modeStr == 'dark';
    }

    // Load Primary Color
    int? colorVal = LocalStorageService.getPrimaryColor();
    if (colorVal != null) {
      _primaryColor = Color(colorVal);
    }

    RhythmaColors.updateTheme(_isDarkMode, _primaryColor);
    notifyListeners();
  }

  Future<void> setDarkMode(bool isDark) async {
    _isDarkMode = isDark;
    RhythmaColors.updateTheme(_isDarkMode, _primaryColor);
    await LocalStorageService.setThemeMode(isDark ? 'dark' : 'light');
    notifyListeners();
  }

  Future<void> setPrimaryColor(Color color) async {
    _primaryColor = color;
    RhythmaColors.updateTheme(_isDarkMode, _primaryColor);
    await LocalStorageService.setPrimaryColor(color.value);
    notifyListeners();
  }
}
