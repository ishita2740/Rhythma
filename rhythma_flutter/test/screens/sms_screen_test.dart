import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/screens/sms/sms_screen.dart';

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

  MockDioResponse defaultHandler(RequestOptions options) {
    switch (options.path) {
      case '/sms/settings':
        return const MockDioResponse(200, {
          'phoneNumber': '+919876543210',
          'enabled': true,
        });
      case '/sms/send-summary':
        return const MockDioResponse(200, {'status': 'sent'});
      default:
        return const MockDioResponse(200, {});
    }
  }

  Future<void> pumpSmsScreen(
    WidgetTester tester, {
    MockDioResponse Function(RequestOptions options)? handler,
  }) async {
    installMockDioAdapter(handler ?? defaultHandler);

    tester.view.physicalSize = const Size(800, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: const SmsScreen(),
      ),
    );
    // The screen loads settings over Dio in didChangeDependencies; give the
    // real event loop a chance to service the mocked request.
    await tester.runAsync(
      () => Future.delayed(const Duration(milliseconds: 200)),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('loads and renders the saved phone number and enabled switch',
      (WidgetTester tester) async {
    await pumpSmsScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(SmsScreen)),
    )!;

    expect(find.text(l10n.smsScreenTitle), findsOneWidget);
    expect(find.text(l10n.smsConfigTitle), findsOneWidget);

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller?.text, '+919876543210');

    final switchWidget = tester.widget<Switch>(find.byType(Switch));
    expect(switchWidget.value, isTrue);

    // Recipient is echoed under "Send a Summary Now".
    expect(find.text('+919876543210'), findsWidgets);
    expect(find.text(l10n.smsSendButton), findsOneWidget);
  });

  testWidgets('treats a 404 from load as a normal first-run state',
      (WidgetTester tester) async {
    await pumpSmsScreen(tester, handler: (options) {
      if (options.path == '/sms/settings') {
        return const MockDioResponse(404, {'detail': 'Not found'});
      }
      return const MockDioResponse(200, {});
    });

    final l10n = AppLocalizations.of(
      tester.element(find.byType(SmsScreen)),
    )!;

    // No error card is shown; the empty state is rendered instead.
    expect(find.text(l10n.smsSendNoPhone), findsOneWidget);
    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller?.text, isEmpty);
  });

  testWidgets('shows a load error card on non-404 failures',
      (WidgetTester tester) async {
    await pumpSmsScreen(tester, handler: (options) {
      if (options.path == '/sms/settings') {
        return const MockDioResponse(500, {'detail': 'backend exploded'});
      }
      return const MockDioResponse(200, {});
    });

    expect(find.text('backend exploded'), findsOneWidget);
  });

  testWidgets('validates the phone number format before saving',
      (WidgetTester tester) async {
    await pumpSmsScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(SmsScreen)),
    )!;

    await tester.enterText(find.byType(TextField), '12345');
    await tester.tap(find.text(l10n.smsSaveSettings));
    await tester.pump();

    expect(find.text(l10n.smsErrorInvalidPhone), findsOneWidget);
  });

  testWidgets('saves settings successfully with a valid phone number',
      (WidgetTester tester) async {
    await pumpSmsScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(SmsScreen)),
    )!;

    await tester.runAsync(() async {
      await tester.tap(find.text(l10n.smsSaveSettings));
      await Future.delayed(const Duration(milliseconds: 400));
    });
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text(l10n.smsSuccessSaved), findsOneWidget);
  });

  testWidgets('sends an on-demand summary to the configured phone',
      (WidgetTester tester) async {
    await pumpSmsScreen(tester);

    final l10n = AppLocalizations.of(
      tester.element(find.byType(SmsScreen)),
    )!;

    await tester.runAsync(() async {
      await tester.tap(find.text(l10n.smsSendButton));
      await Future.delayed(const Duration(milliseconds: 400));
    });
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text(l10n.smsSuccessSent), findsOneWidget);
  });
}
