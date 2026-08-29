import 'package:flutter/material.dart';

/// Represents a language currently officially supported and exposed by the product.
///
/// Note: The repository may contain generated localization files (.arb, etc.)
/// for more locales than are listed here. This list explicitly controls which
/// languages are available for users to select in the UI and validate against.
class SupportedLanguage {
  final String code;
  final String nativeName;

  const SupportedLanguage({
    required this.code,
    required this.nativeName,
  });

  Locale get locale => Locale(code);
}

/// The canonical source of truth for all product-supported languages.
const List<SupportedLanguage> appSupportedLanguages = [
  SupportedLanguage(code: 'en', nativeName: 'English'),
  SupportedLanguage(code: 'hi', nativeName: 'हिन्दी'),
  SupportedLanguage(code: 'ta', nativeName: 'தமிழ்'),
  SupportedLanguage(code: 'te', nativeName: 'తెలుగు'),
  SupportedLanguage(code: 'mr', nativeName: 'मराठी'),
  SupportedLanguage(code: 'gu', nativeName: 'ગુજરાતી'),
  SupportedLanguage(code: 'kn', nativeName: 'ಕನ್ನಡ'),
  SupportedLanguage(code: 'ml', nativeName: 'മലയാളം'),
];
