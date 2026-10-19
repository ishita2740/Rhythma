import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/services/assistant_service.dart';
import 'package:rhythma/services/local_storage_service.dart';
import 'package:rhythma/services/report_service.dart';

import '../test_helpers/dio_mock_adapter.dart';
import '../test_helpers/local_storage_fixture.dart';

class MockAssistantService extends AssistantService {
  bool chatCalled = false;
  String? lastMessage;
  final String reply;
  final bool shouldThrow;

  MockAssistantService({
    this.reply = 'Factual AI summary: cycle regularity is high.',
    this.shouldThrow = false,
  });

  @override
  Future<String> chat(
    String message, {
    String language = 'en',
    List<Map<String, String>> history = const [],
  }) async {
    chatCalled = true;
    lastMessage = message;
    if (shouldThrow) {
      throw const AssistantException('Network connection failed');
    }
    return reply;
  }
}

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

  group('ReportService Symptom Aggregation', () {
    test('aggregates repeated symptoms with occurrences and latest dates', () {
      final logs = [
        {
          'start_date': '2026-08-10',
          'symptoms': ['cramps', 'headache'],
        },
        {
          'start_date': '2026-07-12',
          'symptoms': ['Cramps', 'bloating'],
        },
        {
          'start_date': '2026-06-14',
          'symptoms': ['cramps', 'bloating', 'fatigue'],
        },
      ];

      final aggregated = ReportService.aggregateSymptoms(logs);

      expect(aggregated.length, 4);

      // 'cramps' occurred 3 times, latest 2026-08-10
      final cramps = aggregated.firstWhere((s) => s.symptom.toLowerCase() == 'cramps');
      expect(cramps.occurrences, 3);
      expect(cramps.mostRecentDate, '2026-08-10');

      // 'bloating' occurred 2 times, latest 2026-07-12
      final bloating = aggregated.firstWhere((s) => s.symptom.toLowerCase() == 'bloating');
      expect(bloating.occurrences, 2);
      expect(bloating.mostRecentDate, '2026-07-12');

      // 'headache' occurred 1 time, latest 2026-08-10
      final headache = aggregated.firstWhere((s) => s.symptom.toLowerCase() == 'headache');
      expect(headache.occurrences, 1);
      expect(headache.mostRecentDate, '2026-08-10');
    });

    test('handles null, empty, and malformed symptom lists safely', () {
      final logs = [
        {
          'start_date': '2026-05-01',
          'symptoms': null,
        },
        {
          'start_date': '2026-05-02',
          'symptoms': [' ', ''],
        },
        {
          'start_date': '2026-05-03',
          'symptoms': 'single_string_symptom',
        },
        {
          'start_date': '2026-05-04',
          // No symptoms key at all
        },
      ];

      final aggregated = ReportService.aggregateSymptoms(logs);
      expect(aggregated.length, 1);
      expect(aggregated.first.symptom, 'single_string_symptom');
      expect(aggregated.first.occurrences, 1);
      expect(aggregated.first.mostRecentDate, '2026-05-03');
    });
  });

  group('ReportService Local Health Calculations (Offline Resilience)', () {
    test('reports "no_data" when cycle logs are empty', () {
      final stats = ReportService.calculateLocalHealthStats([], {});
      expect(stats['status'], 'no_data');
      expect(stats['averageCycleLength'], 'No data logged yet');
    });

    test('computes average cycle length, sleep, and stress from local records', () {
      final logs = [
        {
          'start_date': '2026-08-01',
          'flow_intensity': 'heavy',
          'sleep_hours': 7.0,
          'stress_level': 2,
        },
        {
          'start_date': '2026-07-04', // 28 days interval
          'flow_intensity': 'medium',
          'sleep_hours': 8.0,
          'stress_level': 3,
        },
        {
          'start_date': '2026-06-06', // 28 days interval
          'flow_intensity': 'medium',
          'sleep_hours': 9.0,
          'stress_level': 4,
        },
      ];
      final profile = {
        'cycle_length': 28,
        'period_duration': 5,
      };

      final stats = ReportService.calculateLocalHealthStats(logs, profile);
      expect(stats['status'], 'available');
      expect(stats['averageCycleLength'], '28 days');
      expect(stats['averageBleedingDuration'], '5 days');
      expect(stats['sleepHours'], '8.0h');
      // Most recent stress level is 2 / 5 (from the latest 2026-08-01 log)
      expect(stats['recentStressLevel'], '2 / 5');
    });

    test('parses sleep values defensively for numbers, valid strings, malformed strings, and missing values', () {
      final logs = [
        {'start_date': '2026-08-01', 'sleep_hours': 7.0}, // valid numeric double
        {'start_date': '2026-07-31', 'sleep_hours': 8}, // valid numeric int
        {'start_date': '2026-07-30', 'sleep_hours': ' 9.0 '}, // valid trimmed numeric string
        {'start_date': '2026-07-29', 'sleep_hours': 'abc7'}, // malformed string: rejected
        {'start_date': '2026-07-28', 'sleep_hours': '7.5h'}, // unit-suffixed string: rejected
        {'start_date': '2026-07-27', 'sleep_hours': ''}, // empty string: ignored
        {'start_date': '2026-07-26', 'sleep_hours': null}, // null: ignored
        {'start_date': '2026-07-25'}, // missing: ignored
        {'start_date': '2026-07-24', 'sleep_hours': double.nan}, // non-finite: ignored
      ];

      // Valid values are 7.0, 8.0, 9.0 -> average is 8.0h
      final stats = ReportService.calculateLocalHealthStats(logs, {});
      expect(stats['status'], 'available');
      expect(stats['sleepHours'], '8.0h');
    });

    test('reports sleep as "Not available" when all sleep records are missing or malformed', () {
      final logs = [
        {'start_date': '2026-08-01', 'sleep_hours': 'invalid_sleep'},
        {'start_date': '2026-07-31', 'sleep_hours': null},
        {'start_date': '2026-07-30'},
      ];

      final stats = ReportService.calculateLocalHealthStats(logs, {});
      expect(stats['status'], 'available');
      expect(stats['sleepHours'], 'Not available');
    });
  });

  group('ReportService PDF Generation & Privacy Rules', () {
    test('explicit profile fields are included; internal metadata is excluded', () async {
      await LocalStorageService.saveProfile({
        'name': 'Aarya Patel',
        'age': 26,
        'cycle_length': 29,
        'period_duration': 5,
        'cycle_regular': true,
        'last_period': '2026-08-01',
        // Internal metadata that should NEVER be in the PDF:
        'avatar': 'assets/avatars/avatar_special.png',
        'avatar_index': 3,
        'notifications_enabled': true,
        'city': 'SecretCity123',
        'internal_token': 'secret_auth_token_xyz',
      });

      final bytes = await ReportService.buildReportPdfBytes(
        includeAiSummary: false,
        includeEmergencyContacts: false,
      );

      expect(bytes, isNotEmpty);
      final pdfContent = latin1.decode(bytes);

      // Clinical fields are present
      expect(pdfContent.contains('Aarya Patel'), isTrue);
      expect(pdfContent.contains('26 years'), isTrue);
      expect(pdfContent.contains('29 days'), isTrue);
      expect(pdfContent.contains('Regular'), isTrue);
      expect(pdfContent.contains('2026-08-01'), isTrue);

      // Internal metadata is NOT dumped into the document
      expect(pdfContent.contains('avatar_special.png'), isFalse);
      expect(pdfContent.contains('SecretCity123'), isFalse);
      expect(pdfContent.contains('secret_auth_token_xyz'), isFalse);
      expect(pdfContent.contains('notifications_enabled'), isFalse);
    });

    test('emergency contacts are excluded by default to protect privacy', () async {
      await LocalStorageService.saveEmergencyContacts([
        {'name': 'ConfidentialContact', 'phone': '+919988776655'},
      ]);

      // By default includeEmergencyContacts is false
      final bytesDefault = await ReportService.buildReportPdfBytes(
        includeEmergencyContacts: false,
      );
      final contentDefault = latin1.decode(bytesDefault);
      expect(contentDefault.contains('+919988776655'), isFalse);
      expect(contentDefault.contains('ConfidentialContact'), isFalse);

      // Only present if explicitly requested
      final bytesIncluded = await ReportService.buildReportPdfBytes(
        includeEmergencyContacts: true,
      );
      final contentIncluded = latin1.decode(bytesIncluded);
      expect(contentIncluded.contains('+919988776655'), isTrue);
      expect(contentIncluded.contains('ConfidentialContact'), isTrue);
    });

    test('AI summarization is strictly opt-in; no network call when consent is false', () async {
      final mockAssistant = MockAssistantService();

      // Consent is OFF (false)
      final bytes = await ReportService.buildReportPdfBytes(
        includeAiSummary: false,
        assistantService: mockAssistant,
      );

      // Must NEVER call AssistantService
      expect(mockAssistant.chatCalled, isFalse);
      final content = latin1.decode(bytes);
      expect(content.contains('AI Health Summary'), isFalse);
    });

    test('AI summarization is called when consent is ON; labelled with disclaimer', () async {
      final mockAssistant = MockAssistantService(
        reply: 'Cycle length exhibits standard 28-day regularity.',
      );

      // Consent is ON (true)
      final bytes = await ReportService.buildReportPdfBytes(
        includeAiSummary: true,
        assistantService: mockAssistant,
      );

      expect(mockAssistant.chatCalled, isTrue);
      final content = latin1.decode(bytes);
      expect(content.contains('AI Health Summary'), isTrue);
      expect(content.contains('Not clinical advice or a medical diagnosis'), isTrue);
      expect(content.contains('Cycle length exhibits standard 28-day regularity.'), isTrue);
    });

    test('AI summary failure omits section cleanly without printing English error placeholder', () async {
      final failingAssistant = MockAssistantService(shouldThrow: true);

      final bytes = await ReportService.buildReportPdfBytes(
        includeAiSummary: true,
        assistantService: failingAssistant,
      );

      final content = latin1.decode(bytes);
      // Section is completely omitted; never prints "No AI summary available"
      expect(content.contains('No AI summary available'), isFalse);
      expect(content.contains('AI Health Summary'), isFalse);
    });

    test('distinguishes dashboard network failure from missing user data', () async {
      // Seed real user cycle logs in Hive
      await LocalStorageService.saveCycleLog({
        'start_date': '2026-08-01',
        'flow_intensity': 'medium',
        'sleep_hours': 7.5,
        'stress_level': 2,
      });

      // Mock Dio returning 500 server failure for /dashboard
      final dio = Dio();
      dio.httpClientAdapter = MockDioAdapter((options) {
        return const MockDioResponse(500, {'detail': 'Server error'});
      });

      final bytes = await ReportService.buildReportPdfBytes(
        dio: dio,
      );

      final content = latin1.decode(bytes);
      // Trustworthy local stats are displayed, NOT raw 'N/A'
      expect(content.contains('7.5h'), isTrue);
      expect(content.contains('2 / 5'), isTrue);
      expect(content.contains('Computed from on-device records'), isTrue);
    });

    test('multi-page pagination handles large history without overflow', () async {
      // Seed 40 cycle logs to create a multi-page document
      for (int i = 1; i <= 40; i++) {
        final month = (i % 12 + 1).toString().padLeft(2, '0');
        final day = (i % 28 + 1).toString().padLeft(2, '0');
        await LocalStorageService.saveCycleLog({
          'start_date': '2024-$month-$day',
          'flow_intensity': i % 2 == 0 ? 'heavy' : 'medium',
          'symptoms': ['cramps', 'fatigue', 'headache'],
          'mood': 'calm',
          'stress_level': 2,
          'sleep_hours': 8.0,
          'notes': 'Cycle entry #$i with comprehensive notes and logs.',
        });
      }

      final doc = await ReportService.buildReportDocument();
      final bytes = await doc.save();

      expect(bytes.length, greaterThan(1000));
      // Must generate more than 1 page without layout errors
      expect(doc.document.pdfPageList.pages.length, greaterThan(1));
    });

    test('includes canonical medical disclaimer at the bottom', () async {
      final bytes = await ReportService.buildReportPdfBytes();
      final content = latin1.decode(bytes);

      const canonicalDisclaimer =
          'This report is an estimate based on self-logged data and is not a medical diagnosis. Please consult a qualified healthcare professional for medical advice.';
      expect(content.contains(canonicalDisclaimer), isTrue);
    });
  });
}
