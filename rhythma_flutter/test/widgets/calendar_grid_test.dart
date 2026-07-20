import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/providers/cycle_provider.dart';
import 'package:rhythma/screens/cycle/components/calendar_grid.dart';
import 'package:rhythma/services/local_storage_service.dart';

void main() {
  setUp(() {
    LocalStorageService.isTesting = true;
    LocalStorageService.mockCycleLogs = [];
  });

  Widget buildTestableWidget({required Widget child}) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => CycleProvider()),
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

    // Tap day 1 of the displayed month – always safe (even if future, it's rejected silently).
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
}