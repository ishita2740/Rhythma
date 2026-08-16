import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:provider/provider.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/screens/profile/profile_screen.dart';
import 'package:rhythma/services/local_storage_service.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/providers/theme_provider.dart';
import 'package:rhythma/providers/profile_provider.dart';
import 'package:rhythma/screens/cycle/components/log_entry_sheet.dart';
import 'test_helpers/platform_channel_mocks.dart';
import 'test_helpers/local_storage_fixture.dart';

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
    await seedEmergencyContacts('test-user', []);

    // Seed a recent cycle log so the dashboard fallback can compute
    // "Cycle Day 12 • Follicular Phase" without hitting the API.
    final now = DateTime.now();
    final lastPeriod = DateTime(now.year, now.month, now.day - 11);
    await seedCycleLogs('test-user', [
      {
        'start_date':
            '${lastPeriod.year}-${lastPeriod.month.toString().padLeft(2, '0')}-${lastPeriod.day.toString().padLeft(2, '0')}',
        'flow_intensity': 'medium',
      },
    ]);

    // Mock FlutterSecureStorage channel method calls to prevent hanging in tests
    const channel =
        MethodChannel('plugins.it_nomads.com/flutter_secure_storage');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (MethodCall methodCall) async {
      return null; // Mock success
    });
  });

  tearDown(() async {
    await tearDownLocalStorage(tempDir);
  });

  // Helper to pump the Profile Screen with a standard test viewport
  Future<void> pumpProfileScreen(WidgetTester tester) async {
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
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: const [
            Locale('en'),
            Locale('hi'),
            Locale('ta'),
            Locale('te'),
            Locale('mr'),
            Locale('bn'),
          ],
          home: const Scaffold(
            body: ProfileScreen(),
          ),
          routes: {
            '/login': (_) => const Scaffold(body: Text('Login Screen')),
          },
        ),
      ),
    );

    // Settle entry animations
    await tester.pumpAndSettle();
  }

  testWidgets('1. Profile details load successfully on start',
      (WidgetTester tester) async {
    await pumpProfileScreen(tester);

    // Verify initial values from mock storage are displayed
    expect(find.text('Aarya Test'), findsOneWidget);
    expect(find.text('30 years old'), findsOneWidget);
    expect(find.text('28 days'), findsOneWidget);
    expect(find.text('Cycle Day 12 • Follicular Phase'), findsOneWidget);
  });

  testWidgets('2. Edit profile flow handles validation and saves updates',
      (WidgetTester tester) async {
    await pumpProfileScreen(tester);

    // Open Edit Profile Bottom Sheet
    await tester.tap(find.text('Edit Profile Information'));
    await tester.pumpAndSettle();

    // Verify sheet is open
    expect(find.text('Edit Profile'), findsOneWidget);

    final nameField = find.ancestor(
      of: find.text('Name'),
      matching: find.byType(TextField),
    );
    final ageField = find.ancestor(
      of: find.text('Age'),
      matching: find.byType(TextField),
    );
    final cycleField = find.ancestor(
      of: find.text('Average Cycle Length (Days)'),
      matching: find.byType(TextField),
    );

    // ── Test Validation Failures ──
    // Enter empty name, invalid age (under 10), and invalid cycle length (over 45)
    await tester.enterText(nameField, '');
    await tester.enterText(ageField, '5');
    await tester.enterText(cycleField, '50');

    // Tap Save Changes
    await tester.tap(find.text('Save Changes'));
    await tester.pumpAndSettle();

    // Assert validation error messages are displayed
    expect(find.text('Please enter a valid name'), findsOneWidget);
    expect(find.text('Please enter a valid age'), findsOneWidget);
    expect(find.text('Please enter a valid cycle length'), findsOneWidget);

    // ── Test Success Flow ──
    // Enter valid details
    await tester.enterText(nameField, 'Aarya Updated');
    await tester.enterText(ageField, '25');
    await tester.enterText(cycleField, '30');

    // Tap Save Changes — the save handler calls Dio which uses real I/O,
    // so we must run inside tester.runAsync to let the HTTP complete.
    await tester.runAsync(() async {
      await tester.tap(find.text('Save Changes'));
      await Future.delayed(const Duration(seconds: 2));
    });
    await tester.pumpAndSettle();

    // Verify sheet is closed and main profile details are updated
    expect(find.text('Edit Profile'), findsNothing);
    expect(find.text('Aarya Updated'), findsOneWidget);
    expect(find.text('25 years old'), findsOneWidget);
    expect(find.text('30 days'), findsOneWidget);

    // Verify changes are written to local storage
    expect(LocalStorageService.getProfile()?['name'], 'Aarya Updated');
    expect(LocalStorageService.getProfile()?['age'], 25);
    expect(LocalStorageService.getProfile()?['cycle_length'], 30);
  });

  testWidgets(
      '3. Emergency contacts CRUD flow works and validates number format',
      (WidgetTester tester) async {
    await pumpProfileScreen(tester);

    // Open Emergency Contacts sheet
    await tester.tap(find.text('Medical Emergency Contact'));
    await tester.pumpAndSettle();

    // Verify initial empty state placeholder
    expect(find.text('No emergency contacts set up yet.'), findsOneWidget);

    // ── Create Contact ──
    // Tap Add New
    await tester.tap(find.text('Add New'));
    await tester.pumpAndSettle();

    final contactNameField =
        find.ancestor(of: find.text('Name'), matching: find.byType(TextField));
    final contactPhoneField =
        find.ancestor(of: find.text('Phone'), matching: find.byType(TextField));

    // Try to save with empty name and invalid phone number
    await tester.enterText(contactNameField, '');
    await tester.enterText(contactPhoneField, 'invalid123');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();

    // Verify error checks
    expect(find.text('Contact name is required'), findsOneWidget);
    expect(find.text('Please enter a valid phone number'), findsOneWidget);

    // Enter valid details
    await tester.enterText(contactNameField, 'Mom');
    await tester.enterText(contactPhoneField, '+919876543210');

    // Tap Save — inside runAsync to ensure any async handlers complete
    await tester.runAsync(() async {
      await tester.tap(find.text('Save'));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();
    // Extra pump to ensure dialog's widget tree is fully removed
    await tester.pump();

    // Verify dialog closes and contact is in list
    expect(find.text('No emergency contacts set up yet.'), findsNothing);
    expect(find.text('Mom'), findsOneWidget);
    expect(find.text('+919876543210'), findsOneWidget);

    final editIconButton = find.byIcon(Icons.edit_rounded).last;
    await tester.tap(editIconButton);
    await tester.pumpAndSettle();

    // Edit Name
    final editNameField =
        find.ancestor(of: find.text('Name'), matching: find.byType(TextField));
    await tester.enterText(editNameField, 'Mother');

    // Tap Save inside runAsync so the dialog's Navigator.pop can complete
    await tester.runAsync(() async {
      await tester.tap(find.text('Save'));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();
    await tester.pump();

    // Verify list is updated
    expect(find.text('Mother'), findsOneWidget);
    expect(find.text('Mom'), findsNothing);

    // ── Delete Contact ──
    // Tap Delete (trash outline icon)
    await tester.runAsync(() async {
      await tester.tap(find.byIcon(Icons.delete_outline_rounded));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();
    await tester.pump();

    // Verify contact is deleted and empty state placeholder is shown again
    expect(find.text('Mother'), findsNothing);
    expect(find.text('No emergency contacts set up yet.'), findsOneWidget);
  });

  testWidgets('4. Settings screen navigation and logout flows work',
      (WidgetTester tester) async {
    await pumpProfileScreen(tester);

    // Tap App Settings
    await tester.tap(find.text('App Settings'));
    await tester.pumpAndSettle();

    // Verify settings screen is opened and header/tiles are present
    expect(find.text('Settings'), findsOneWidget);
    expect(find.text('App Preferences'), findsOneWidget);
    expect(find.text('Security & Privacy'), findsOneWidget);

    // Tap Log Out button pinned at the bottom-side
    await tester.tap(find.text('Log Out'));
    await tester.pumpAndSettle();

    // Verify Log Out confirmation dialog is shown
    expect(find.text('Are you sure you want to log out of Rhythma?'),
        findsOneWidget);

    // Tap Cancel — inside runAsync so the dialog's Navigator.pop completes
    await tester.runAsync(() async {
      await tester.tap(find.text('Cancel'));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();
    await tester.pump();

    // Verify dialog closes and settings screen remains
    expect(find.text('Are you sure you want to log out of Rhythma?'),
        findsNothing);
    expect(find.text('Settings'), findsOneWidget);

    // Tap Log Out again to test confirm logout
    await tester.tap(find.text('Log Out'));
    await tester.pumpAndSettle();

    // Tap Log Out inside the confirmation dialog (which is an ElevatedButton)
    final dialogLogoutButton = find.descendant(
      of: find.byType(ElevatedButton),
      matching: find.text('Log Out'),
    );
    // Confirm tap — inside runAsync so the dialog's Navigator.pop completes
    // and the async AuthService.logout handler finishes.
    await tester.runAsync(() async {
      await tester.tap(dialogLogoutButton);
      await Future.delayed(const Duration(seconds: 2));
    });
    await tester.pumpAndSettle();
    await tester.pump();

    // Logout intentionally clears only the auth session (JWT) — local
    // device data (profile, emergency contacts) is treated as a
    // persistent on-device health record and deliberately survives
    // logout, so a user isn't greeted with a wiped-looking profile just
    // from signing out and back in. See settings_screen.dart and
    // LocalStorageService.clearAll()'s doc comment for the full rationale.
    // Verify local data is preserved in the Hive box directly (scoped
    // to the last user id even after currentUserId is cleared).
    final box = Hive.box<Map>('user_profile');
    expect(box.get('test-user::profile'), isNotNull);
    expect(box.get('test-user::profile')?['name'], 'Aarya Test');
    expect(LocalStorageService.currentUserId, isNull);
  });

  testWidgets('5. Log Entry Sheet create, edit, save flows',
      (WidgetTester tester) async {
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
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () {
                  LogEntrySheet.show(
                    context,
                    DateTime(2023, 10, 1),
                    existingLog: {
                      'start_date': '2023-10-01',
                      'flow_intensity': 'Medium',
                      'mood': '😌',
                      'sleep_hours': 7,
                      'stress_level': 2,
                      'symptoms': ['Cramps', 'Fatigue'],
                    },
                  );
                },
                child: const Text('Open Sheet'),
              ),
            ),
          ),
        ),
      ),
    );

    // Open the sheet
    await tester.tap(find.text('Open Sheet'));
    await tester.pumpAndSettle();

    // Verify UI rendering and pre-filled data
    expect(find.text('Log your day'), findsOneWidget);

    // Check flow intensity
    expect(find.text('Medium'), findsWidgets);

    // Check mood emoji
    expect(find.text('😌'), findsWidgets);

    // Check symptoms
    expect(find.text('Cramps'), findsWidgets);
    expect(find.text('Fatigue'), findsWidgets);

    // Interact with chips
    await tester.tap(find.text('Nausea'));
    await tester.pumpAndSettle();

    // Save — the handler calls saveCycleLog (Hive) then Navigator.pop.
    // Use runAsync to ensure the dialog pop completes.
    await tester.runAsync(() async {
      await tester.tap(find.text('Save Log'));
      await Future.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    // Sheet should be closed
    expect(find.text('Log your day'), findsNothing);
  });

  testWidgets(
      '6. Cycle Tracking and Wellness Tips toggles show a confirmation '
      'dialog and only change state when confirmed',
      (WidgetTester tester) async {
    mockNotificationPlatformChannels(
      permissionGranted: true,
      initTimezones: false,
    );

    await pumpProfileScreen(tester);

    await tester.tap(find.text('App Settings'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));

    // Cycle Tracking Reminders defaults to ON.
    final cycleSwitch =
        find.widgetWithText(SwitchListTile, 'Cycle Tracking Reminders');
    expect(tester.widget<SwitchListTile>(cycleSwitch).value, isTrue);

    // Tapping it off should prompt for confirmation rather than flipping
    // immediately.
    await tester.tap(cycleSwitch);
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(
      find.text('Are you sure you want to turn OFF cycle tracking reminders?'),
      findsOneWidget,
    );

    // Cancelling leaves the switch untouched.
    await tester.tap(find.text('Cancel'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(tester.widget<SwitchListTile>(cycleSwitch).value, isTrue);

    // Wellness Tips defaults to OFF; same confirm flow turning it ON.
    final wellnessSwitch = find.widgetWithText(SwitchListTile, 'Wellness Tips');
    expect(tester.widget<SwitchListTile>(wellnessSwitch).value, isFalse);

    await tester.tap(wellnessSwitch);
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(
      find.text('Are you sure you want to turn ON wellness tips?'),
      findsOneWidget,
    );
    await tester.tap(find.text('Confirm'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(tester.widget<SwitchListTile>(wellnessSwitch).value, isTrue);
  });

  testWidgets(
      '7. Medicine Alerts toggle requests notification permission and '
      'schedules/cancels the alert accordingly',
      (WidgetTester tester) async {
    // Medicine Alerts is the one toggle that talks to NotificationService
    // (permission_handler + flutter_local_notifications), so we stub both
    // plugins' platform channels first — see test_helpers for why.
    mockNotificationPlatformChannels(permissionGranted: true);

    await pumpProfileScreen(tester);
    await tester.tap(find.text('App Settings'));
    await tester.pumpAndSettle();

    final medicineSwitch = find.widgetWithText(SwitchListTile, 'Medicine Alerts');
    expect(tester.widget<SwitchListTile>(medicineSwitch).value, isTrue);

    // Turn OFF: confirm dialog, then SettingsScreen cancels the pending
    // local notification.
    await tester.tap(medicineSwitch);
    await tester.pumpAndSettle();
    expect(
      find.text('Are you sure you want to turn OFF medicine alerts?'),
      findsOneWidget,
    );
    await tester.tap(find.text('Confirm'));
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(medicineSwitch).value, isFalse);

    // Turn back ON: confirm dialog, then SettingsScreen requests
    // notification permission and schedules a new alert. With the platform
    // channels mocked as granted, this should complete without throwing.
    await tester.tap(medicineSwitch);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm'));
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(medicineSwitch).value, isTrue);
  });
}
