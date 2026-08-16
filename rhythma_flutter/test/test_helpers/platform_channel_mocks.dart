// ignore_for_file: depend_on_referenced_packages

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;
import 'package:flutter_local_notifications_platform_interface/flutter_local_notifications_platform_interface.dart';
import 'package:plugin_platform_interface/plugin_platform_interface.dart';

class FakeLocalNotificationsPlatform extends FlutterLocalNotificationsPlatform
    with MockPlatformInterfaceMixin {
  @override
  dynamic noSuchMethod(Invocation invocation) => Future.value(null);

  @override
  Future<void> cancel({required int id}) async {}

  @override
  Future<void> cancelAll() async {}

  @override
  Future<void> cancelAllPendingNotifications() async {}

  @override
  Future<void> show({
    required int id,
    String? title,
    String? body,
    String? payload,
  }) async {}

  @override
  Future<void> zonedSchedule({
    required int id,
    String? title,
    String? body,
    required tz.TZDateTime scheduledDate,
    String? payload,
    DateTimeComponents? matchDateTimeComponents,
  }) async {}
}

/// Sets up a mock [FlutterLocalNotificationsPlatform] and mocks the method
/// channels for `permission_handler` and `flutter_local_notifications`.
///
/// When [initTimezones] is `true` (default), also initializes timezone
/// data (needed by `zonedSchedule` / `scheduleMedicineAlert`). Tests that
/// only call `cancelNotification` can pass `false` to skip the slow
/// timezone database load.
void mockNotificationPlatformChannels({
  bool permissionGranted = true,
  bool initTimezones = true,
}) {
  TestWidgetsFlutterBinding.ensureInitialized();

  if (initTimezones) {
    tz.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Kolkata'));
  }

  FlutterLocalNotificationsPlatform.instance = FakeLocalNotificationsPlatform();

  const MethodChannel permissionChannel =
      MethodChannel('plugins.flutter.io/permissions');
  const MethodChannel notificationChannel =
      MethodChannel('dexterous.com/flutter_local_notifications');

  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(permissionChannel,
          (MethodCall methodCall) async {
    if (methodCall.method == 'requestPermissions') {
      return {0: permissionGranted ? 1 : 0};
    }
    if (methodCall.method == 'checkPermissionStatus') {
      return permissionGranted ? 1 : 0;
    }
    return null;
  });

  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(notificationChannel,
          (MethodCall methodCall) async {
    if (methodCall.method == 'initialize') {
      return true;
    }
    return null;
  });
}