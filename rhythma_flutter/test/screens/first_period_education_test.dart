import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/screens/education/first_period_education_screen.dart';

void main() {
  testWidgets('FirstPeriodEducationScreen renders all educational cards correctly',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: FirstPeriodEducationScreen(),
      ),
    );

    expect(find.text('First Period & Cycle Guide'), findsOneWidget);
    expect(find.textContaining('What is a Menstrual Cycle?'), findsOneWidget);
    expect(find.textContaining('Hygiene & Care Basics'), findsOneWidget);
    expect(find.textContaining('Easy Cramp Relief Tips'), findsOneWidget);
  });
}
