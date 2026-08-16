import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/services/local_storage_service.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp('hive_locale_test');
    Hive.init(tempDir.path);
    await Hive.openBox<dynamic>('settings');
  });

  tearDown(() async {
    await Hive.close();
    if (tempDir.existsSync()) tempDir.deleteSync(recursive: true);
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

    test('rejects unsupported locale', () {
      final provider = LocaleProvider();
      final initialLocale = provider.locale.languageCode;

      // bn is not in the product-supported list yet
      provider.setLocale(const Locale('bn'));

      // It should remain unchanged
      expect(provider.locale.languageCode, initialLocale);
      expect(LocalStorageService.preferredLanguage, initialLocale);
    });
  });
}
