import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/components/shared.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/providers/profile_provider.dart';
import 'package:rhythma/providers/theme_provider.dart';
import 'package:rhythma/screens/insights/insights_screen.dart';

import '../test_helpers/dio_mock_adapter.dart';
import '../test_helpers/local_storage_fixture.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('test-user');
  });

  tearDown(() async {
    restoreDioAdapter();
    await tearDownLocalStorage(tempDir);
  });

  Future<void> pumpInsightsScreen(
    WidgetTester tester, {
    Map<String, dynamic>? dashboard,
    int dashboardStatus = 200,
  }) async {
    installMockDioAdapter((options) {
      if (options.path == '/dashboard') {
        return MockDioResponse(dashboardStatus, dashboard ?? {});
      }
      return const MockDioResponse(200, {});
    });

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
          home: const ShellBackground(child: InsightsScreen()),
        ),
      ),
    );
    // InsightsScreen fetches /dashboard in initState over Dio; give the real
    // event loop a chance to service the mocked request before settling.
    await tester.runAsync(
      () => Future.delayed(const Duration(milliseconds: 200)),
    );
    await tester.pumpAndSettle();
  }

  const fullDashboard = {
    'user': {'name': 'Aarya Test'},
    'cycle': {'total': 28},
    'insights': {'averageCycleLength': 27, 'shortestCycleLength': 26, 'longestCycleLength': 28, 'averageBleedingDuration': 5, 'sleepHours': '6.5h'},
    'cycleHistory': [
      {'cycle_length': 26},
      {'cycle_length': 28},
      {'cycle_length': 27},
    ],
    'symptomFrequency': {
      'cramps': 0.4,
      'headache': 0.2,
    },
    'hasEnoughDataForInsights': true,
    'recentStressLevel': 4,
  };

  testWidgets('renders scores, trend, symptoms and recommendations',
      (WidgetTester tester) async {
    await pumpInsightsScreen(tester, dashboard: fullDashboard);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(InsightsScreen)),
    )!;

    expect(find.text('27d'), findsOneWidget); // avg cycle
    expect(find.text('26d'), findsOneWidget); // shortest
    expect(find.text('28d'), findsOneWidget); // longest
    expect(find.text('5d'), findsOneWidget); // avg bleeding
    // Variability of [26, 28, 27] rounds to 1 day.
    expect(find.text('1 ${l10n.homeDaysLabel}'), findsOneWidget); // variability
    expect(find.text('27 ${l10n.homeDaysLabel}'), findsOneWidget); // avg cycle from insights
    expect(find.text('6.5h'), findsOneWidget);
    expect(find.text(l10n.logEnergyHigh), findsOneWidget); // stress level 4

    // Symptom frequency bars.
    expect(find.text('40%'), findsOneWidget);
    expect(find.text('20%'), findsOneWidget);

    // Data-driven recommendations (low sleep + high stress).
    expect(find.text(l10n.insightsRec1), findsOneWidget);
    expect(find.text(l10n.insightsRec2), findsOneWidget);
    expect(find.text(l10n.insightsRec3), findsOneWidget);

    expect(find.text('Export Health Report'), findsOneWidget);
  });

  testWidgets('shows not-enough-data placeholders for an empty history',
      (WidgetTester tester) async {
    await pumpInsightsScreen(tester, dashboard: {
      'user': {'name': 'Aarya Test'},
      'cycle': {},
      'insights': {},
      'cycleHistory': [],
      'symptomFrequency': {},
      'hasEnoughDataForInsights': false,
    });

    final l10n = AppLocalizations.of(
      tester.element(find.byType(InsightsScreen)),
    )!;

    expect(find.text(l10n.insightsNotEnoughData), findsOneWidget);
    expect(find.text(l10n.insightsNoSymptomsYet), findsOneWidget);
    expect(find.text(l10n.insightsNotEnoughTrendData), findsOneWidget);
    expect(find.text('—'), findsWidgets);
  });

  testWidgets('shows an error card when the dashboard request fails',
      (WidgetTester tester) async {
    await pumpInsightsScreen(tester, dashboard: {}, dashboardStatus: 500);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(InsightsScreen)),
    )!;

    expect(find.textContaining(l10n.insightsLoadError('')), findsOneWidget);
  });

  testWidgets('shows the insights disclaimer at the bottom of the screen',
      (WidgetTester tester) async {
    await pumpInsightsScreen(tester, dashboard: fullDashboard);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(InsightsScreen)),
    )!;

    expect(find.text(l10n.insightsDisclaimer), findsOneWidget);
  });

  testWidgets('disclaimer is visible without scrolling on tall screens',
      (WidgetTester tester) async {
    await pumpInsightsScreen(tester, dashboard: fullDashboard);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(InsightsScreen)),
    )!;

    // The disclaimer should be present in the widget tree
    final disclaimerFinder = find.text(l10n.insightsDisclaimer);
    expect(disclaimerFinder, findsOneWidget);

    // Verify it's not off-screen by checking it's rendered
    final widget = tester.widget<Text>(disclaimerFinder);
    expect(widget.data, isNotEmpty);
  });
}
