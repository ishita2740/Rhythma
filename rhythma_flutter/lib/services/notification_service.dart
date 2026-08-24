import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tz;
import 'package:timezone/timezone.dart' as tz;
import 'package:permission_handler/permission_handler.dart';

import '../l10n/app_localizations.dart';
import 'local_storage_service.dart';
import 'reminder_schedule.dart';

/// Scheduling and delivering the app's notifications.
///
/// Both automatic reminders used to be unreliable in the same way, and it
/// was invisible: every failure was a bare `return`, so the toggle in
/// Settings stayed switched on while nothing was registered with the OS
/// (issue #511).
///
/// * The period reminder projected exactly one cycle from `last_period`.
///   Once that date passed it was permanently in the past, so the method
///   returned without scheduling — on that launch and every launch after.
///   The anchor only moves when a period is logged, so the reminder
///   worked for the woman already logging and switched itself off for the
///   woman who had stopped, who is the one it exists to reach.
/// * The logging reminder was documented as daily and scheduled as a
///   one-shot: no `matchDateTimeComponents`, and an early return for
///   anyone opening the app after 19:00 — which is when people check a
///   tracker.
/// * Every `NotificationDetails` was Android-only, so nothing presented on
///   iOS at all, and the alert permission was never requested through the
///   plugin there either.
/// * `scheduleAllAutomaticNotifications` skipped a disabled reminder
///   rather than cancelling it, so one already registered with the OS kept
///   being delivered after its toggle was turned off.
///
/// The arithmetic now lives in `reminder_schedule.dart` as pure functions,
/// where it can be tested without the plugin, a device or the wall clock.
/// What is left here is the part that genuinely needs the plugin.
class NotificationService {
  NotificationService._();
  static final NotificationService instance = NotificationService._();

  final FlutterLocalNotificationsPlugin _notificationsPlugin =
      FlutterLocalNotificationsPlugin();

  bool _isInitialized = false;

  // Notification IDs
  static const int _periodPredictionId = 2001;
  static const int _loggingReminderId = 2002;

  /// How far ahead of the projected period date to fire.
  static const int defaultDaysBefore = 2;

  Future<void> init() async {
    if (_isInitialized) return;

    tz.initializeTimeZones();

    const AndroidInitializationSettings initializationSettingsAndroid =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    // Permissions are still requested later, from `requestPermissions()`,
    // rather than at first launch — asking before the user has seen what
    // the reminders are for is how an app gets denied permanently. What
    // changed is that `requestPermissions()` now actually asks on iOS.
    const DarwinInitializationSettings initializationSettingsIOS =
        DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );

    const InitializationSettings initializationSettings =
        InitializationSettings(
      android: initializationSettingsAndroid,
      iOS: initializationSettingsIOS,
    );

    await _notificationsPlugin.initialize(
      settings: initializationSettings,
      onDidReceiveNotificationResponse: (NotificationResponse response) {
        // Handle notification tap
      },
    );

    _isInitialized = true;
  }

  /// Ask for permission on whichever platform this is.
  ///
  /// `permission_handler` covers Android's POST_NOTIFICATIONS. On iOS that
  /// call does not obtain the alert permission the plugin needs, which is
  /// why nothing was ever delivered there — the Darwin init flags are all
  /// false, and nothing asked afterwards. The iOS request goes through the
  /// plugin's own resolver.
  Future<bool> requestPermissions() async {
    final iosPlugin = _notificationsPlugin.resolvePlatformSpecificImplementation<
        IOSFlutterLocalNotificationsPlugin>();
    if (iosPlugin != null) {
      final granted = await iosPlugin.requestPermissions(
        alert: true,
        badge: true,
        sound: true,
      );
      return granted ?? false;
    }

    var status = await Permission.notification.status;
    if (status.isDenied) {
      status = await Permission.notification.request();
    }
    return status.isGranted;
  }

  // ── Notification details ────────────────────────────────────────────
  //
  // Every one of these carries an `iOS:` entry. Without it the plugin has
  // nothing to present on that platform and the notification is silently
  // dropped, which is what was happening to all four.

  NotificationDetails _details({
    required String channelId,
    required String channelName,
    required String channelDescription,
    Importance importance = Importance.max,
    Priority priority = Priority.high,
  }) {
    return NotificationDetails(
      android: AndroidNotificationDetails(
        channelId,
        channelName,
        channelDescription: channelDescription,
        importance: importance,
        priority: priority,
        playSound: true,
      ),
      iOS: const DarwinNotificationDetails(
        presentAlert: true,
        presentBadge: true,
        presentSound: true,
      ),
    );
  }

  /// The strings for a notification, in the language the user chose.
  ///
  /// A notification is composed outside the widget tree, so there is no
  /// `BuildContext` to read `AppLocalizations.of()` from. The generated
  /// `lookupAppLocalizations` takes a `Locale` directly, and the chosen
  /// language is already on the device in settings — so a reminder can be
  /// written in the reader's own language instead of the English these
  /// were hard-coded in.
  AppLocalizations get _l10n {
    try {
      return lookupAppLocalizations(
        Locale(LocalStorageService.preferredLanguage),
      );
    } catch (_) {
      // An unsupported code stored by an older build, or a settings box
      // that is not open on this path. English is a worse notification
      // than the right language and a much better one than a crash on a
      // background scheduling pass, which would take the reminder with it.
      return lookupAppLocalizations(const Locale('en'));
    }
  }

  Future<void> scheduleMedicineAlert(
      {required int id,
      required String title,
      required String body,
      required DateTime scheduledDate}) async {
    final tz.TZDateTime tzDate = tz.TZDateTime.from(scheduledDate, tz.local);

    if (tzDate.isBefore(tz.TZDateTime.now(tz.local))) {
      return;
    }

    await _notificationsPlugin.zonedSchedule(
      id: id.abs() % 0x7FFFFFFF,
      title: title,
      body: body,
      scheduledDate: tzDate,
      notificationDetails: _details(
        channelId: 'medicine_channel',
        channelName: 'Medicine Alerts',
        channelDescription: 'Reminders for your medication',
      ),
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
    );
  }

  Future<void> showInstantNotification({
    required int id,
    required String title,
    required String body,
  }) async {
    await _notificationsPlugin.show(
      id: id,
      title: title,
      body: body,
      // Was `('test_channel', 'Test Alerts')`. Android channel names are
      // user-visible in system notification settings, so shipping one
      // literally called "Test Alerts" in a health app reads as a build
      // that escaped.
      notificationDetails: _details(
        channelId: 'rhythma_reminders_channel',
        channelName: _l10n.notificationChannelReminders,
        channelDescription: 'Reminders and alerts from Rhythma',
      ),
    );
  }

  /// Schedule the period reminder, rolling forward past a stale anchor.
  ///
  /// Returns what was scheduled, so a caller — and a test — can tell the
  /// three outcomes apart instead of watching a method return `void`
  /// whether it did anything or not.
  Future<PeriodReminderKind> schedulePeriodPredictionReminder({
    int daysBefore = defaultDaysBefore,
    DateTime? now,
  }) async {
    final profile = LocalStorageService.getProfile();
    if (profile == null) return PeriodReminderKind.none;

    final plan = planPeriodReminder(
      lastPeriod: DateTime.tryParse(profile['last_period'] as String? ?? ''),
      cycleLength: (profile['cycle_length'] as num?)?.toInt(),
      daysBefore: daysBefore,
      now: now ?? DateTime.now(),
    );

    if (!plan.shouldSchedule) return PeriodReminderKind.none;

    final l10n = _l10n;
    final tz.TZDateTime tzDate = tz.TZDateTime.from(plan.at!, tz.local);

    final isLogNudge = plan.kind == PeriodReminderKind.logPeriod;

    await _notificationsPlugin.zonedSchedule(
      id: _periodPredictionId,
      title: isLogNudge
          ? l10n.notificationLogPeriodTitle
          : l10n.notificationPeriodTitle,
      body: isLogNudge
          ? l10n.notificationLogPeriodBody
          : l10n.notificationPeriodBody('$daysBefore'),
      scheduledDate: tzDate,
      notificationDetails: _details(
        channelId: 'period_prediction_channel',
        channelName: 'Period Predictions',
        channelDescription: 'Reminders for your upcoming period',
      ),
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
    );

    return plan.kind;
  }

  /// Schedule the daily reminder to log, at [hour]:[minute].
  ///
  /// Genuinely daily now: `matchDateTimeComponents: DateTimeComponents.time`
  /// makes the OS repeat it, and the time rolls to tomorrow when today's
  /// has already gone instead of returning and scheduling nothing.
  ///
  /// The "already logged today" check deliberately no longer gates
  /// scheduling. It was evaluated once, at launch, so a woman who opened
  /// the app at 08:00 and logged at 09:00 was still nudged at 19:00 to do
  /// what she had already done — and, worse, one who had logged at launch
  /// got no reminder scheduled for any later day either.
  Future<void> scheduleLoggingReminder({
    int hour = 19,
    int minute = 0,
    DateTime? now,
  }) async {
    final at = nextDailyOccurrence(
      now: now ?? DateTime.now(),
      hour: hour,
      minute: minute,
    );

    final l10n = _l10n;

    await _notificationsPlugin.zonedSchedule(
      id: _loggingReminderId,
      title: l10n.notificationLogReminderTitle,
      body: l10n.notificationLogReminderBody,
      scheduledDate: tz.TZDateTime.from(at, tz.local),
      notificationDetails: _details(
        channelId: 'logging_reminder_channel',
        channelName: 'Logging Reminders',
        channelDescription: 'Nudges to log your daily cycle data',
        importance: Importance.defaultImportance,
        priority: Priority.defaultPriority,
      ),
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      // Without this the whole thing is one notification at one instant.
      matchDateTimeComponents: DateTimeComponents.time,
    );
  }

  /// Cancel all automatic notifications (period prediction and logging reminders).
  Future<void> cancelAutomaticNotifications() async {
    await cancelNotification(_periodPredictionId);
    await cancelNotification(_loggingReminderId);
  }

  /// Reconcile what the OS holds with what the toggles say.
  ///
  /// Every launch, both directions. It used to only ever *add*: with one
  /// toggle on and one off the early return was skipped and the disabled
  /// reminder's already-registered notification was left in place, so a
  /// reminder switched off in Settings kept arriving.
  Future<void> scheduleAllAutomaticNotifications() async {
    if (LocalStorageService.periodPredictionReminders) {
      await schedulePeriodPredictionReminder();
    } else {
      await cancelNotification(_periodPredictionId);
    }

    if (LocalStorageService.loggingReminders) {
      await scheduleLoggingReminder();
    } else {
      await cancelNotification(_loggingReminderId);
    }
  }

  Future<void> cancelAll() async {
    await _notificationsPlugin.cancelAll();
  }

  Future<void> cancelNotification(int id) async {
    await _notificationsPlugin.cancel(id: id);
  }
}
