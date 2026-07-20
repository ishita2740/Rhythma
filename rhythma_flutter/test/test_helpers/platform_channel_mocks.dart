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
  dynamic noSuchMethod(Invocation invocation) {
    return Future.value(null);
  }
}

// Added the optional named parameter to match what widget_test.dart wants
void mockNotificationPlatformChannels({bool permissionGranted = true}) {
  TestWidgetsFlutterBinding.ensureInitialized();

  // Initialize local timezone databases
  tz.initializeTimeZones();
  tz.setLocalLocation(tz.getLocation('Asia/Kolkata'));

  // Mock the late-initialized notification platform instance
  FlutterLocalNotificationsPlatform.instance = FakeLocalNotificationsPlatform();

  // Setup standard MethodChannel interceptors
  const MethodChannel permissionChannel = MethodChannel('plugins.flutter.io/permissions');
  const MethodChannel notificationChannel = MethodChannel('dexterous.com/flutter_local_notifications');

  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(permissionChannel, (MethodCall methodCall) async {
    if (methodCall.method == 'requestPermissions') {
      // Return 1 (granted) or 0 (denied) based on the test parameters
      return {0: permissionGranted ? 1 : 0}; 
    }
    if (methodCall.method == 'checkPermissionStatus') {
      return permissionGranted ? 1 : 0;
    }
    return null;
  });

  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(notificationChannel, (MethodCall methodCall) async {
    if (methodCall.method == 'initialize') {
      return true;
    }
    return null;
  });
}