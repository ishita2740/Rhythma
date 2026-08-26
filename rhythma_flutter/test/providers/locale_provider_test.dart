import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/services/local_storage_service.dart';

import '../test_helpers/local_storage_fixture.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await LocalStorageService.init(testPath: tempDir.path);
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  group('LocaleProvider', () {
    test('initializes with default preferred language', () {
      final provider = LocaleProvider();
      expect(provider.locale.languageCode, 'en');
    });

    test('accepts supported locale', () {
      final provider = LocaleProvider();
      provider.setLocale(const Locale('hi'));
      expect(provider.locale.languageCode, 'hi');
      expect(LocalStorageService.preferredLanguage, 'hi');
    });

    test('accepts Bengali locale', () {
      final provider = LocaleProvider();
      provider.setLocale(const Locale('bn'));
      expect(provider.locale.languageCode, 'bn');
      expect(LocalStorageService.preferredLanguage, 'bn');
    });

    test('rejects unsupported locale', () {
      final provider = LocaleProvider();
      final initialLocale = provider.locale.languageCode;

      // fr is not in the product-supported list
      provider.setLocale(const Locale('fr'));

      // It should remain unchanged
      expect(provider.locale.languageCode, initialLocale);
      expect(LocalStorageService.preferredLanguage, initialLocale);
    });
  });
}
