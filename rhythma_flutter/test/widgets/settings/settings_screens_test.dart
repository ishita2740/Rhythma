import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/providers/theme_provider.dart';
import 'package:rhythma/providers/profile_provider.dart'; // <-- added import
import 'package:rhythma/screens/settings/language_screen.dart';
import 'package:rhythma/screens/settings/theme_screen.dart';
import 'package:rhythma/services/local_storage_service.dart';

void main() {
  setUp(() {
    LocalStorageService.isTesting = true;
  });

  Future<void> pumpScreen(
    WidgetTester tester,
    Widget screen, {
    LocaleProvider? localeProvider,
    ThemeProvider? themeProvider,
  }) async {
    tester.view.physicalSize = const Size(800, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => localeProvider ?? LocaleProvider()),
          ChangeNotifierProvider(create: (_) => themeProvider ?? ThemeProvider()),
          ChangeNotifierProvider(create: (_) => ProfileProvider()), // <-- added
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: screen,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  group('LanguageScreen', () {
    testWidgets('lists every supported language with English selected by default',
        (WidgetTester tester) async {
      await pumpScreen(tester, const LanguageScreen());

      expect(find.text('Select Language'), findsOneWidget);

      for (final langName in LanguageScreen.languages.keys) {
        expect(find.text(langName), findsOneWidget);
      }

      expect(
        find.descendant(
          of: find.widgetWithText(ListTile, 'English'),
          matching: find.byIcon(Icons.check_circle_rounded),
        ),
        findsOneWidget,
      );
      expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);
    });

    testWidgets('tapping a language updates LocaleProvider and moves the checkmark',
        (WidgetTester tester) async {
      final localeProvider = LocaleProvider();
      await pumpScreen(tester, const LanguageScreen(), localeProvider: localeProvider);

      await tester.tap(find.text('हिन्दी (Hindi)'));
      await tester.pumpAndSettle();

      expect(localeProvider.locale.languageCode, 'hi');
      expect(
        find.descendant(
          of: find.widgetWithText(ListTile, 'हिन्दी (Hindi)'),
          matching: find.byIcon(Icons.check_circle_rounded),
        ),
        findsOneWidget,
      );
      expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);
    });
  });

  group('ThemeScreen', () {
    testWidgets('dark mode switch reflects and toggles ThemeProvider.isDarkMode',
        (WidgetTester tester) async {
      final themeProvider = ThemeProvider();
      await pumpScreen(tester, const ThemeScreen(), themeProvider: themeProvider);

      expect(find.text('Theme toggle'), findsOneWidget);

      final darkModeSwitch = find.widgetWithText(SwitchListTile, 'Dark Mode');
      expect(tester.widget<SwitchListTile>(darkModeSwitch).value, isFalse);
      expect(themeProvider.isDarkMode, isFalse);

      await tester.tap(darkModeSwitch);
      await tester.pumpAndSettle();

      expect(tester.widget<SwitchListTile>(darkModeSwitch).value, isTrue);
      expect(themeProvider.isDarkMode, isTrue);
    });

    testWidgets('tapping a swatch updates ThemeProvider.primaryColor',
        (WidgetTester tester) async {
      final themeProvider = ThemeProvider();
      await pumpScreen(tester, const ThemeScreen(), themeProvider: themeProvider);

      expect(find.text('Theme Color'), findsOneWidget);

      final rosePink =
          ThemeScreen.predefinedColors[1]['color'] as Color;
      expect(themeProvider.primaryColor, isNot(rosePink));

      final swatchFinder = find.byWidgetPredicate((widget) {
        if (widget is! Container) return false;
        final decoration = widget.decoration;
        return decoration is BoxDecoration && decoration.color == rosePink;
      });
      expect(swatchFinder, findsOneWidget);

      await tester.tap(swatchFinder);
      await tester.pumpAndSettle();

      expect(themeProvider.primaryColor, rosePink);
    });
  });
}