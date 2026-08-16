import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/screens/cycle/components/log_entry_sheet.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

void main() {
  group('LogEntrySheet Sleep Slider Bounds', () {
    Widget buildTestWidget({Map<String, dynamic>? existingLog}) {
      return MaterialApp(
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: LogEntrySheet(
            date: DateTime(2023, 10, 1),
            existingLog: existingLog,
          ),
        ),
      );
    }

    testWidgets('slider initializes to 8h if no log provided', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      final sliderFinder = find.byType(Slider);
      expect(sliderFinder, findsWidgets); // Contains multiple sliders (sleep, stress)
      
      final Slider sleepSlider = tester.widget(sliderFinder.first);
      expect(sleepSlider.value, 8.0);
      expect(sleepSlider.min, 2.0);
      expect(sleepSlider.max, 14.0);
      expect(sleepSlider.divisions, 12);
    });

    testWidgets('slider clamps to 2.0 if log has less than 2.0', (tester) async {
      await tester.pumpWidget(buildTestWidget(existingLog: {'sleep_hours': 1.0}));
      await tester.pumpAndSettle();

      final sliderFinder = find.byType(Slider);
      final Slider sleepSlider = tester.widget(sliderFinder.first);
      
      expect(sleepSlider.value, 2.0); // Clamped
    });

    testWidgets('slider clamps to 14.0 if log has more than 14.0', (tester) async {
      await tester.pumpWidget(buildTestWidget(existingLog: {'sleep_hours': 20.0}));
      await tester.pumpAndSettle();

      final sliderFinder = find.byType(Slider);
      final Slider sleepSlider = tester.widget(sliderFinder.first);
      
      expect(sleepSlider.value, 14.0); // Clamped
    });

    testWidgets('slider uses exact log value if within bounds', (tester) async {
      await tester.pumpWidget(buildTestWidget(existingLog: {'sleep_hours': 9.0}));
      await tester.pumpAndSettle();

      final sliderFinder = find.byType(Slider);
      final Slider sleepSlider = tester.widget(sliderFinder.first);
      
      expect(sleepSlider.value, 9.0);
    });
  });
}
