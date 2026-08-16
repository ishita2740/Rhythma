import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/providers/cycle_provider.dart';
import 'package:rhythma/screens/cycle/components/log_entry_sheet.dart';
import 'package:rhythma/services/local_storage_service.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'test_helpers/local_storage_fixture.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    tempDir = await setUpLocalStorage();
    await seedCurrentUserId('test-user');
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  group('LocalStorageService.deleteCycleLog', () {
    test('removes an existing log entry', () async {
      await LocalStorageService.saveCycleLog({
        'start_date': '2025-10-01',
        'flow_intensity': 'Medium',
        'mood': '😀',
      });

      expect(
        LocalStorageService.getCycleLogForDate(DateTime(2025, 10, 1)),
        isNotNull,
      );

      await LocalStorageService.deleteCycleLog('2025-10-01');

      expect(
        LocalStorageService.getCycleLogForDate(DateTime(2025, 10, 1)),
        isNull,
      );
    });

    test('does not throw when deleting a non-existent log', () async {
      await expectLater(
        LocalStorageService.deleteCycleLog('1999-01-01'),
        completes,
      );
    });

    test('does not affect other days', () async {
      await LocalStorageService.saveCycleLog({
        'start_date': '2025-10-01',
        'flow_intensity': 'Medium',
      });
      await LocalStorageService.saveCycleLog({
        'start_date': '2025-10-02',
        'flow_intensity': 'Light',
      });

      await LocalStorageService.deleteCycleLog('2025-10-01');

      expect(
        LocalStorageService.getCycleLogForDate(DateTime(2025, 10, 1)),
        isNull,
      );
      expect(
        LocalStorageService.getCycleLogForDate(DateTime(2025, 10, 2)),
        isNotNull,
      );
    });
  });

  group('LogEntrySheet delete button', () {
    testWidgets('shows delete button when editing an existing log',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider(create: (_) => CycleProvider()),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: const [
              Locale('en'),
              Locale('bn'),
            ],
            home: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () {
                  LogEntrySheet.show(
                    context,
                    DateTime(2025, 10, 1),
                    existingLog: {
                      'start_date': '2025-10-01',
                      'flow_intensity': 'Medium',
                      'mood': '😀',
                    },
                  );
                },
                child: const Text('Open Sheet'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open Sheet'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.delete_outline_rounded), findsOneWidget);
    });

    testWidgets('hides delete button when creating a new log',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider(create: (_) => CycleProvider()),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: const [
              Locale('en'),
              Locale('bn'),
            ],
            home: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () {
                  LogEntrySheet.show(
                    context,
                    DateTime(2025, 10, 1),
                  );
                },
                child: const Text('Open Sheet'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open Sheet'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.delete_outline_rounded), findsNothing);
    });

    testWidgets('shows confirmation dialog then cancels',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        MultiProvider(
          providers: [
            ChangeNotifierProvider(create: (_) => CycleProvider()),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: const [
              Locale('en'),
              Locale('bn'),
            ],
            home: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () {
                  LogEntrySheet.show(
                    context,
                    DateTime(2025, 10, 1),
                    existingLog: {
                      'start_date': '2025-10-01',
                      'flow_intensity': 'Medium',
                      'mood': '😀',
                    },
                  );
                },
                child: const Text('Open Sheet'),
              ),
            ),
          ),
        ),
      );

      // Open the sheet
      await tester.tap(find.text('Open Sheet'));
      await tester.pumpAndSettle();

      // Tap delete icon to open confirmation dialog
      await tester.tap(find.byIcon(Icons.delete_outline_rounded));
      await tester.pumpAndSettle();

      expect(find.text('Delete Entry'), findsOneWidget);
      expect(
        find.text(
          'Are you sure you want to delete this day\'s log? This cannot be undone.',
        ),
        findsOneWidget,
      );

      // Cancel the deletion
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
    });
  });
}
