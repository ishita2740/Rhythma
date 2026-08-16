import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/models/cycle_log.dart';
import 'package:rhythma/providers/cycle_provider.dart';
import 'package:rhythma/screens/cycle/components/calendar_grid.dart';
import 'package:rhythma/services/local_storage_service.dart';
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

  Widget buildTestableWidget({required Widget child, CycleProvider? cycleProvider}) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => cycleProvider ?? CycleProvider()),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: child,
        ),
      ),
    );
  }

  testWidgets('CalendarGrid renders and handles date selection',
      (WidgetTester tester) async {
    final pageController = PageController(initialPage: 12000);

    await tester.pumpWidget(buildTestableWidget(
      child: CalendarGrid(
        pageController: pageController,
        initialPageOffset: 12000,
      ),
    ));

    await tester.pumpAndSettle();

    // Tap day 1 of the displayed month – always safe.
    await tester.tap(find.text('1').first);
    await tester.pump();

    // Verify the calendar still renders.
    expect(find.text('1'), findsWidgets);
  });

  testWidgets('CalendarGrid supports month swiping via PageController',
      (WidgetTester tester) async {
    final pageController = PageController(initialPage: 12000);

    await tester.pumpWidget(buildTestableWidget(
      child: CalendarGrid(
        pageController: pageController,
        initialPageOffset: 12000,
      ),
    ));
    await tester.pumpAndSettle();

    // Swipe left (next month)
    pageController.nextPage(
        duration: const Duration(milliseconds: 100), curve: Curves.linear);
    await tester.pumpAndSettle();

    // Ensure the calendar still renders.
    expect(find.text('1'), findsWidgets);
  });

  testWidgets(
      'Calendar markers reflect real Hive data and do not fallback to hardcoded mock state (#131)',
      (WidgetTester tester) async {
    final now = DateTime.now();
    final seededDate = DateTime(now.year, now.month, 15);

    await tester.runAsync(() async {
      await seedCycleLogs('test-user', [
        CycleLog(
          startDate: seededDate,
          flowIntensity: 'medium',
          symptoms: ['cramps'],
        ).toJson(),
      ]);
    });

    final cycleProvider = CycleProvider();
    final pageController = PageController(initialPage: 12000);

    await tester.pumpWidget(buildTestableWidget(
      cycleProvider: cycleProvider,
      child: CalendarGrid(
        pageController: pageController,
        initialPageOffset: 12000,
      ),
    ));
    await tester.pumpAndSettle();

    expect(cycleProvider.hasLogsForDate(seededDate), isTrue);

    final unloggedDate = DateTime(now.year, now.month, 28);
    if (unloggedDate.day != seededDate.day) {
      expect(cycleProvider.hasLogsForDate(unloggedDate), isFalse);
    }
  });
}
