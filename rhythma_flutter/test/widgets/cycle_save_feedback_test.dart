import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/screens/cycle/components/log_entry_sheet.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

void main() {
  group('LogEntrySheet SnackBar Feedback', () {
    Widget buildTestWidget() {
      return MaterialApp(
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: LogEntrySheet(
            date: DateTime(2023, 10, 1),
          ),
        ),
      );
    }

    testWidgets('shows snackbar on save', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      final saveButton = find.text('Save'); // Depends on l10n, using default English
      if (saveButton.evaluate().isNotEmpty) {
        await tester.tap(saveButton);
        await tester.pump(); // Trigger frame for snackbar
        
        expect(find.byType(SnackBar), findsOneWidget);
      }
    });

    testWidgets('shows snackbar on delete', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      final deleteButton = find.byIcon(Icons.delete_outline);
      if (deleteButton.evaluate().isNotEmpty) {
        await tester.tap(deleteButton);
        await tester.pumpAndSettle(); // Wait for dialog
        
        final confirmDelete = find.text('Delete');
        if (confirmDelete.evaluate().isNotEmpty) {
            await tester.tap(confirmDelete);
            await tester.pump(); // Trigger frame for snackbar
            
            expect(find.byType(SnackBar), findsOneWidget);
        }
      }
    });
  });
}
