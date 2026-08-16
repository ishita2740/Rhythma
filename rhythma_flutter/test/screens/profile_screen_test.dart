import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/providers/profile_provider.dart';
import 'package:rhythma/providers/theme_provider.dart';
import 'package:rhythma/screens/profile/profile_screen.dart';

import '../test_helpers/local_storage_fixture.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('test-user');
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  Future<void> pumpProfileScreen(WidgetTester tester) async {
    tester.view.physicalSize = const Size(800, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => LocaleProvider()),
          ChangeNotifierProvider(create: (_) => ThemeProvider()),
          ChangeNotifierProvider(create: (_) => ProfileProvider()),
        ],
        child: MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const Scaffold(body: ProfileScreen()),
          routes: {
            '/login': (_) => const Scaffold(body: Text('Login Screen')),
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('renders default values when no profile is saved yet',
      (WidgetTester tester) async {
    await pumpProfileScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(ProfileScreen)),
    )!;

    expect(find.text('Aarya'), findsOneWidget);
    expect(find.text('28 ${l10n.profileYearsOld}'), findsOneWidget);
    expect(find.text('28 ${l10n.homeDaysLabel}'), findsWidgets);
  });

  testWidgets('renders the seeded profile values from local storage',
      (WidgetTester tester) async {
    await tester.runAsync(
      () => seedProfile('test-user', {
            'name': 'Mira',
            'age': 27,
            'cycle_length': 30,
          }),
    );
    await pumpProfileScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(ProfileScreen)),
    )!;

    expect(find.text('Mira'), findsOneWidget);
    expect(find.text('27 ${l10n.profileYearsOld}'), findsOneWidget);
    expect(find.text('30 ${l10n.homeDaysLabel}'), findsWidgets);
  });
}
