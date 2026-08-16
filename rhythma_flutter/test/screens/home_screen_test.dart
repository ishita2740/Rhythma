import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/providers/profile_provider.dart';
import 'package:rhythma/providers/theme_provider.dart';
import 'package:rhythma/screens/home/home_screen.dart';
import 'package:rhythma/services/local_storage_service.dart';

import '../test_helpers/dio_mock_adapter.dart';
import '../test_helpers/local_storage_fixture.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('test-user');
    await seedProfile('test-user', {
      'name': 'Aarya Test',
      'age': 30,
      'cycle_length': 28,
    });
  });

  tearDown(() async {
    restoreDioAdapter();
    await tearDownLocalStorage(tempDir);
  });

  Future<void> pumpHomeScreen(WidgetTester tester) async {
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
          home: const Scaffold(body: HomeScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('fetches and renders dashboard data from the backend',
      (WidgetTester tester) async {
    // Start with the backend down so the error state is reachable.
    installMockDioAdapter(
      (options) => const MockDioResponse(500, {'detail': 'server down'}),
    );
    await pumpHomeScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(HomeScreen)),
    )!;
    expect(find.text(l10n.homeFailedLoad), findsOneWidget);

    // The backend comes back; retry re-fetches and renders the data.
    installMockDioAdapter((options) {
      if (options.path == '/dashboard') {
        return const MockDioResponse(200, {
          'user': {'name': 'Aarya Test'},
          'cycle': {'nextPeriodDays': 12, 'day': 3, 'total': 28},
          'insights': {'averageCycleLength': 28, 'averageBleedingDuration': 5, 'sleepHours': '8.1h'},
        });
      }
      return const MockDioResponse(200, {});
    });

    // runAsync so the fetch's Hive cache write (real file I/O) completes.
    await tester.runAsync(() async {
      await tester.tap(find.text(l10n.homeRetry));
      await Future.delayed(const Duration(milliseconds: 400));
    });
    await tester.pumpAndSettle();

    expect(find.text('${l10n.homeGreeting}, Aarya Test'), findsOneWidget);
    expect(find.text('28d'), findsOneWidget); // Avg Cycle
    expect(find.text('5d'), findsOneWidget); // Bleeding
    expect(find.text('8.1h'), findsOneWidget); // Sleep
    expect(find.text('12'), findsOneWidget); // Next period in N days
    expect(find.text(l10n.homeWeeklyInsightLabel), findsOneWidget);
  });

  testWidgets('falls back to the cached dashboard when the API fails',
      (WidgetTester tester) async {
    // Seed the cache in the real zone first so _loadCachedDashboard can
    // render it synchronously during pumpWidget.
    await tester.runAsync(
      () => LocalStorageService.saveCachedDashboard({
        'user': {'name': 'Cached User'},
        'cycle': {'nextPeriodDays': 3, 'day': 5, 'total': 30},
        'insights': {'averageCycleLength': 28, 'averageBleedingDuration': 5, 'sleepHours': '6.5h'},
      }),
    );
    installMockDioAdapter((options) => const MockDioResponse(500, {
          'detail': 'server down',
        }));

    await pumpHomeScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(HomeScreen)),
    )!;

    expect(find.text('28d'), findsOneWidget); // avg cycle
    expect(find.text('5d'), findsOneWidget); // avg bleeding
    expect(find.text('6.5h'), findsOneWidget);
  });

  testWidgets('shows an error state with retry when loading fails',
      (WidgetTester tester) async {
    installMockDioAdapter((options) => const MockDioResponse(500, {
          'detail': 'server down',
        }));

    await pumpHomeScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(HomeScreen)),
    )!;
    expect(find.text(l10n.homeFailedLoad), findsOneWidget);
    expect(find.text(l10n.homeRetry), findsOneWidget);
  });

  testWidgets('quick-log flow saves a flow entry and shows a confirmation',
      (WidgetTester tester) async {
    await tester.runAsync(
      () => LocalStorageService.saveCachedDashboard({
        'user': {'name': 'Aarya Test'},
        'cycle': {'nextPeriodDays': 12, 'day': 3, 'total': 28},
        'insights': {'averageCycleLength': 28, 'averageBleedingDuration': 5, 'sleepHours': '8.1h'},
      }),
    );
    installMockDioAdapter((options) {
      if (options.path == '/cycle/log') {
        return const MockDioResponse(200, {});
      }
      return const MockDioResponse(500, {'detail': 'down'});
    });

    await pumpHomeScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(HomeScreen)),
    )!;

    await tester.tap(find.text(l10n.homeLogFlow));
    await tester.pumpAndSettle();

    expect(find.text('Log ${l10n.homeLogFlow}'), findsOneWidget);
    expect(find.text(l10n.logMedium), findsOneWidget);

    // runAsync so the quick-log Hive write + /cycle/log POST complete.
    await tester.runAsync(() async {
      await tester.tap(find.text(l10n.logMedium));
      await Future.delayed(const Duration(milliseconds: 500));
    });
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Log ${l10n.homeLogFlow}'), findsNothing);
    expect(
      find.text('${l10n.homeLogFlow} logged: ${l10n.logMedium}'),
      findsOneWidget,
    );

    // Saved locally (Hive is the source of truth).
    final log =
        LocalStorageService.getCycleLogForDate(DateTime.now());
    expect(log?['flow_intensity'], 'medium');
  });

  testWidgets('SOS header icon shows a no-contacts snackbar when unconfigured',
      (WidgetTester tester) async {
    await tester.runAsync(
      () => LocalStorageService.saveCachedDashboard({
        'user': {'name': 'Aarya Test'},
        'cycle': {'nextPeriodDays': 12, 'day': 3, 'total': 28},
        'insights': {'averageCycleLength': 28, 'averageBleedingDuration': 5, 'sleepHours': '8.1h'},
      }),
    );
    installMockDioAdapter((options) => const MockDioResponse(500, {
          'detail': 'down',
        }));

    await pumpHomeScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(HomeScreen)),
    )!;

    await tester.tap(find.byIcon(Icons.sos_rounded));
    await tester.pump();

    expect(find.text(l10n.profileNoContacts), findsOneWidget);
  });
}
