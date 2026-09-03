import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tz;
import 'package:timezone/timezone.dart' as tz;
import 'package:permission_handler/permission_handler.dart';
import 'local_storage_service.dart';
import 'cycle_service.dart';

class NotificationService {
  NotificationService._();
  static final NotificationService instance = NotificationService._();

  final FlutterLocalNotificationsPlugin _notificationsPlugin =
      FlutterLocalNotificationsPlugin();

  bool _isInitialized = false;

  // Notification IDs
  static const int _periodPredictionId = 2001;
  static const int _loggingReminderId = 2002;

  Future<void> init() async {
    if (_isInitialized) return;

    tz.initializeTimeZones();

    const AndroidInitializationSettings initializationSettingsAndroid =
        AndroidInitializationSettings('@mipmap/ic_launcher');

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

  Future<bool> requestPermissions() async {
    var status = await Permission.notification.status;
    if (status.isDenied) {
      status = await Permission.notification.request();
    }
    return status.isGranted;
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

    const AndroidNotificationDetails androidPlatformChannelSpecifics =
        AndroidNotificationDetails(
      'medicine_channel',
      'Medicine Alerts',
      channelDescription: 'Reminders for your medication',
      importance: Importance.max,
      priority: Priority.high,
      playSound: true,
    );

    const NotificationDetails platformChannelSpecifics =
        NotificationDetails(android: androidPlatformChannelSpecifics);

    await _notificationsPlugin.zonedSchedule(
      id: id.abs() % 0x7FFFFFFF,
      title: title,
      body: body,
      scheduledDate: tzDate,
      notificationDetails: platformChannelSpecifics,
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
    );
  }

  Future<void> showInstantNotification({
    required int id,
    required String title,
    required String body,
  }) async {
    const AndroidNotificationDetails androidPlatformChannelSpecifics =
        AndroidNotificationDetails(
      'test_channel',
      'Test Alerts',
      importance: Importance.max,
      priority: Priority.high,
    );

    const NotificationDetails platformChannelSpecifics =
        NotificationDetails(android: androidPlatformChannelSpecifics);

    await _notificationsPlugin.show(
      id: id,
      title: title,
      body: body,
      notificationDetails: platformChannelSpecifics,
    );
  }

  /// Schedule a notification before the predicted next period date.
  ///
  /// Fetches the prediction from the backend `GET /cycle/predictions` so the
  /// reminder uses the server's outlier-rejected cycle-length estimate
  /// instead of naive `lastPeriod + cycleLength` math.  Falls back to the
  /// local profile when the network is unavailable.
  Future<void> schedulePeriodPredictionReminder({int daysBefore = 2}) async {
    DateTime? predictedDate;
    int? confidence;

    try {
      final prediction = await CycleService().getPrediction();
      if (prediction != null) {
        final dateStr = prediction['nextPeriodDate'] as String?;
        if (dateStr != null) {
          predictedDate = DateTime.tryParse(dateStr);
        }
        confidence = _confidenceToLevel(prediction['confidence'] as String?);
      }
    } catch (_) {
      // Backend unreachable — fall through to local profile.
    }

    // Fallback: derive prediction from the local profile.
    predictedDate ??= _localPrediction();

    if (predictedDate == null) return;

    final now = DateTime.now();
    final reminderDate = predictedDate.subtract(Duration(days: daysBefore));
    if (reminderDate.isBefore(now)) return;

    final tz.TZDateTime tzDate = tz.TZDateTime.from(reminderDate, tz.local);

    const AndroidNotificationDetails androidPlatformChannelSpecifics =
        AndroidNotificationDetails(
      'period_prediction_channel',
      'Period Predictions',
      channelDescription: 'Reminders for your upcoming period',
      importance: Importance.max,
      priority: Priority.high,
      playSound: true,
    );

    const NotificationDetails platformChannelSpecifics =
        NotificationDetails(android: androidPlatformChannelSpecifics);

    final confidenceLabel = _confidenceLabel(confidence);
    final body = confidenceLabel != null
        ? 'Your period is expected to start in $daysBefore days '
            '($confidenceLabel confidence). Get your supplies ready!'
        : 'Your period is expected to start in $daysBefore days. '
            'Get your supplies ready!';

    await _notificationsPlugin.zonedSchedule(
      id: _periodPredictionId,
      title: 'Period Expected Soon',
      body: body,
      scheduledDate: tzDate,
      notificationDetails: platformChannelSpecifics,
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
    );
  }

  /// Local fallback when the backend is unreachable.
  DateTime? _localPrediction() {
    final profile = LocalStorageService.getProfile();
    if (profile == null) return null;

    final lastPeriodStr = profile['last_period'] as String?;
    if (lastPeriodStr == null) return null;

    final lastPeriod = DateTime.tryParse(lastPeriodStr);
    if (lastPeriod == null) return null;

    final cycleLength = (profile['cycle_length'] as num?)?.toInt() ?? 28;
    return lastPeriod.add(Duration(days: cycleLength));
  }

  static int? _confidenceToLevel(String? c) {
    if (c == null) return null;
    switch (c.toLowerCase()) {
      case 'high':
        return 3;
      case 'medium':
        return 2;
      case 'low':
        return 1;
      default:
        return null;
    }
  }

  static String? _confidenceLabel(int? level) {
    if (level == null) return null;
    if (level >= 3) return 'high';
    if (level >= 2) return 'medium';
    if (level >= 1) return 'low';
    return null;
  }

  /// Schedule a daily reminder to log cycle data if the user has not logged
  /// anything for today. The notification fires at [hour]:[minute] (default 7 PM).
  Future<void> scheduleLoggingReminder({int hour = 19, int minute = 0}) async {
    final now = DateTime.now();
    final todayLog = LocalStorageService.getCycleLogForDate(now);
    if (todayLog != null) return;

    var scheduledDate = DateTime(now.year, now.month, now.day, hour, minute);
    if (scheduledDate.isBefore(now)) return;

    final tz.TZDateTime tzDate = tz.TZDateTime.from(scheduledDate, tz.local);

    const AndroidNotificationDetails androidPlatformChannelSpecifics =
        AndroidNotificationDetails(
      'logging_reminder_channel',
      'Logging Reminders',
      channelDescription: 'Nudges to log your daily cycle data',
      importance: Importance.defaultImportance,
      priority: Priority.defaultPriority,
      playSound: true,
    );

    const NotificationDetails platformChannelSpecifics =
        NotificationDetails(android: androidPlatformChannelSpecifics);

    await _notificationsPlugin.zonedSchedule(
      id: _loggingReminderId,
      title: 'Time to Log Your Day',
      body: 'You haven\'t logged any cycle data today. '
          'Take a moment to track how you\'re feeling!',
      scheduledDate: tzDate,
      notificationDetails: platformChannelSpecifics,
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
    );
  }

  /// Cancel all automatic notifications (period prediction and logging reminders).
  Future<void> cancelAutomaticNotifications() async {
    await cancelNotification(_periodPredictionId);
    await cancelNotification(_loggingReminderId);
  }

  /// Reschedule all automatic notifications based on current settings.
  Future<void> scheduleAllAutomaticNotifications() async {
    if (!LocalStorageService.periodPredictionReminders &&
        !LocalStorageService.loggingReminders) {
      return;
    }

    if (LocalStorageService.periodPredictionReminders) {
      await schedulePeriodPredictionReminder();
    }
    if (LocalStorageService.loggingReminders) {
      await scheduleLoggingReminder();
    }
  }

  Future<void> cancelAll() async {
    await _notificationsPlugin.cancelAll();
  }

  Future<void> cancelNotification(int id) async {
    await _notificationsPlugin.cancel(id: id);
  }
}
