import 'package:flutter/material.dart';

/// Rhythma design tokens — mirrors the web CSS :root variables exactly.
class RhythmaColors {
  // Primary
  static Color primary = const Color(0xFF9B72CF);
  static Color primaryFg = const Color(0xFFFCFAFF);
  static Color lavender = const Color(0xFFD8C8F0);

  // Rose Pink  (oklch 0.72 0.14 350 ≈)
  static const Color rose = Color(0xFFE07AAD);
  static const Color roseFg = Color(0xFFFCFAFF);

  // Teal  (oklch 0.68 0.10 195)
  static const Color teal = Color(0xFF52B3B0);
  static const Color tealFg = Color(0xFFFCFAFF);

  // Warm Coral  (oklch 0.74 0.13 35)
  static const Color coral = Color(0xFFE8946A);
  static const Color coralFg = Color(0xFFFCFAFF);

  // Backgrounds
  static Color background = const Color(0xFFFDF8FF);
  static Color backgroundEnd = const Color(0xFFF8EEF8);
  static Color surface = const Color(0xFFFFFFFF);
  static Color surfaceMuted = const Color(0xFFF5F0FA);

  // Foreground
  static Color foreground = const Color(0xFF2D1F47);
  static Color mutedFg = const Color(0xFF7A6E8A);

  // Border
  static Color border = const Color(0xFFE8DFF5);

  static bool isDark = false;

  // Glass card helper — used many places
  static Color get glassCard => surface.withOpacity(0.75);
  static Color get glassBorder => lavender.withOpacity(0.4);

  static void updateTheme(bool isDarkMode, Color selectedPrimary) {
    isDark = isDarkMode;
    if (isDarkMode) {
      // In dark mode, keep the background dark but use the selected primary color
      primary = selectedPrimary;
      primaryFg = const Color(0xFFFCFAFF);
      lavender = selectedPrimary.withOpacity(0.3);

      background = const Color(0xFF121212);
      backgroundEnd = const Color(0xFF1E1E1E);
      surface = const Color(0xFF1E1E1E);
      surfaceMuted = const Color(0xFF2C2C2C);
      foreground = const Color(0xFFFDF8FF);
      mutedFg = const Color(0xFFAAA4B0);
      border = const Color(0xFF333333);
    } else {
      // In light mode, apply the custom primary color
      primary = selectedPrimary;
      primaryFg = selectedPrimary.computeLuminance() > 0.5
          ? const Color(0xFF2D1F47)
          : const Color(0xFFFCFAFF);
      lavender = selectedPrimary.withOpacity(0.3);

      // Adapt the background to the chosen color
      background = Color.alphaBlend(
          selectedPrimary.withOpacity(0.04), const Color(0xFFFFFFFF));
      backgroundEnd = Color.alphaBlend(
          selectedPrimary.withOpacity(0.10), const Color(0xFFFFFFFF));
      surface = const Color(0xFFFFFFFF);
      surfaceMuted = Color.alphaBlend(
          selectedPrimary.withOpacity(0.07), const Color(0xFFFFFFFF));

      foreground = const Color(0xFF2D1F47);
      mutedFg = const Color(0xFF7A6E8A);
      border = Color.alphaBlend(
          selectedPrimary.withOpacity(0.15), const Color(0xFFFFFFFF));
    }
  }
}

class RhythmaGradients {
  static LinearGradient get primary => LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [RhythmaColors.primary, RhythmaColors.rose],
      );

  static LinearGradient get bg => LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [RhythmaColors.background, RhythmaColors.backgroundEnd],
      );

  static LinearGradient tinted(Color color) => LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          color.withOpacity(0.18),
          color.withOpacity(0.08),
        ],
      );
}

class RhythmaTheme {
  static ThemeData get theme {
    final colorScheme = RhythmaColors.isDark
        ? ColorScheme.dark(
            primary: RhythmaColors.primary,
            secondary: RhythmaColors.teal,
            tertiary: RhythmaColors.rose,
            surface: RhythmaColors.surface,
            onPrimary: RhythmaColors.primaryFg,
            onSecondary: RhythmaColors.tealFg,
            onSurface: RhythmaColors.foreground,
          )
        : ColorScheme.light(
            primary: RhythmaColors.primary,
            secondary: RhythmaColors.teal,
            tertiary: RhythmaColors.rose,
            surface: RhythmaColors.surface,
            onPrimary: RhythmaColors.primaryFg,
            onSecondary: RhythmaColors.tealFg,
            onSurface: RhythmaColors.foreground,
          );

    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Nunito',
      brightness: RhythmaColors.isDark ? Brightness.dark : Brightness.light,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: Colors.transparent,
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        iconTheme: IconThemeData(color: RhythmaColors.foreground),
        titleTextStyle: TextStyle(
          color: RhythmaColors.foreground,
          fontSize: 20,
          fontWeight: FontWeight.w700,
          fontFamily: 'Nunito',
        ),
      ),
      textTheme: TextTheme(
        displayLarge: TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w700,
          color: RhythmaColors.foreground,
          height: 1.2,
        ),
        titleLarge: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: RhythmaColors.foreground,
        ),
        titleMedium: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
          color: RhythmaColors.foreground,
        ),
        bodyLarge: TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w400,
          color: RhythmaColors.foreground,
          height: 1.5,
        ),
        bodyMedium: TextStyle(
          fontSize: 14,
          color: RhythmaColors.foreground,
          height: 1.4,
        ),
        labelSmall: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: RhythmaColors.mutedFg,
          letterSpacing: 0.8,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: RhythmaColors.primary,
          foregroundColor: RhythmaColors.primaryFg,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: RhythmaColors.surfaceMuted,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: RhythmaColors.primary, width: 1.5),
        ),
        hintStyle: TextStyle(
          color: RhythmaColors.mutedFg,
          fontSize: 14,
        ),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      ),
    );
  }
}
