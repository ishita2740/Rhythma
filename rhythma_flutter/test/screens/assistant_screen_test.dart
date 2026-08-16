import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/providers/profile_provider.dart';
import 'package:rhythma/providers/theme_provider.dart';
import 'package:rhythma/screens/assistant/assistant_screen.dart';

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

    installMockDioAdapter((options) {
      if (options.path == '/assistant/chat') {
        return const MockDioResponse(200, {
          'response': 'Drink more water and rest.',
        });
      }
      return const MockDioResponse(200, {});
    });
  });

  tearDown(() async {
    restoreDioAdapter();
    await tearDownLocalStorage(tempDir);
  });

  Future<void> pumpAssistantScreen(WidgetTester tester) async {
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
          home: const AssistantScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('shows a personalized welcome and suggested prompts',
      (WidgetTester tester) async {
    await pumpAssistantScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(AssistantScreen)),
    )!;

    // The welcome bubble is rendered as a rich-text message.
    expect(
      find.textContaining('Aarya Test', findRichText: true),
      findsOneWidget,
    );
    expect(find.text(l10n.assistantSug1), findsOneWidget);
    expect(find.text(l10n.assistantSug2), findsOneWidget);
    expect(find.text(l10n.assistantInputHint), findsOneWidget);
  });

  testWidgets('sending a message appends the user bubble and the reply',
      (WidgetTester tester) async {
    await pumpAssistantScreen(tester);

    await tester.enterText(find.byType(TextField), 'Is my cycle normal?');

    // runAsync so the Hive chat-history write (real file I/O) completes.
    await tester.runAsync(() async {
      await tester.tap(find.byIcon(Icons.send_rounded));
      await Future.delayed(const Duration(milliseconds: 400));
    });
    await tester.pumpAndSettle();

    expect(find.text('Is my cycle normal?'), findsOneWidget);
    expect(
      find.textContaining('Drink more water and rest.', findRichText: true),
      findsOneWidget,
    );

    // Suggested prompts disappear once a conversation has started.
    final l10n = AppLocalizations.of(
      tester.element(find.byType(AssistantScreen)),
    )!;
    expect(find.text(l10n.assistantSug1), findsNothing);
  });

  testWidgets('restores persisted chat history on startup',
      (WidgetTester tester) async {
    // runAsync so the real Hive write completes (fake-zone I/O would hang).
    await tester.runAsync(
      () => Hive.box('settings').put('test-user::chat_history', [
            {'role': 'user', 'content': 'What is my cycle phase?'},
            {'role': 'model', 'content': 'You are in your follicular phase.'},
          ]),
    );

    await pumpAssistantScreen(tester);

    expect(find.text('What is my cycle phase?'), findsOneWidget);
    expect(
      find.textContaining('follicular phase', findRichText: true),
      findsOneWidget,
    );
  });

  testWidgets('shows an error bubble when the assistant call fails',
      (WidgetTester tester) async {
    installMockDioAdapter(
      (options) => const MockDioResponse(500, {'detail': 'backend down'}),
    );

    await pumpAssistantScreen(tester);

    await tester.enterText(find.byType(TextField), 'Hello');
    await tester.runAsync(() async {
      await tester.tap(find.byIcon(Icons.send_rounded));
      await Future.delayed(const Duration(milliseconds: 400));
    });
    await tester.pumpAndSettle();

    expect(find.text('Hello'), findsOneWidget);
    expect(find.textContaining('Error:', findRichText: true), findsOneWidget);
  });
}
