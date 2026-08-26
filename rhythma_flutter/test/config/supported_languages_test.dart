import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/config/supported_languages.dart';

void main() {
  group('Supported Languages', () {
    test('contains the expected 9 product-supported locales', () {
      final codes = appSupportedLanguages.map((l) => l.code).toList();

      expect(codes.length, 9);
      expect(codes,
          containsAll(['en', 'hi', 'ta', 'te', 'mr', 'gu', 'kn', 'ml', 'bn']));
    });

    test('no duplicate codes exist', () {
      final codes = appSupportedLanguages.map((l) => l.code).toList();
      final uniqueCodes = codes.toSet();

      expect(codes.length, equals(uniqueCodes.length));
    });
  });
}
