import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:rhythma/services/api_client.dart';
import 'package:rhythma/services/assistant_service.dart';
import 'package:rhythma/services/local_storage_service.dart';

/// Aggregated symptom frequency entry for clinical health reporting.
class SymptomFrequency {
  final String symptom;
  int occurrences;
  String mostRecentDate;

  SymptomFrequency({
    required this.symptom,
    required this.occurrences,
    required this.mostRecentDate,
  });
}

class ReportService {
  /// Aggregates raw cycle log symptoms by name, counting occurrences and
  /// tracking the most recent date logged. Safely handles missing/malformed fields.
  static List<SymptomFrequency> aggregateSymptoms(
    List<Map<String, dynamic>> cycleLogs,
  ) {
    final Map<String, SymptomFrequency> map = {};

    for (final log in cycleLogs) {
      final date = log['start_date']?.toString() ?? '';
      final raw = log['symptoms'];
      final List<String> list = [];

      if (raw is List) {
        for (final item in raw) {
          if (item != null) {
            final s = item.toString().trim();
            if (s.isNotEmpty) list.add(s);
          }
        }
      } else if (raw is String) {
        final s = raw.trim();
        if (s.isNotEmpty) list.add(s);
      }

      for (final item in list) {
        final key = item.toLowerCase();
        if (!map.containsKey(key)) {
          map[key] = SymptomFrequency(
            symptom: item,
            occurrences: 1,
            mostRecentDate: date,
          );
        } else {
          final entry = map[key]!;
          entry.occurrences += 1;
          if (date.isNotEmpty &&
              (entry.mostRecentDate.isEmpty ||
                  date.compareTo(entry.mostRecentDate) > 0)) {
            entry.mostRecentDate = date;
          }
        }
      }
    }

    final result = map.values.toList();
    result.sort((a, b) {
      final cmp = b.occurrences.compareTo(a.occurrences);
      if (cmp != 0) return cmp;
      return b.mostRecentDate.compareTo(a.mostRecentDate);
    });
    return result;
  }

  /// Calculates trustworthy health metrics directly from local on-device logs
  /// and profile data to guarantee offline reliability and avoid misrepresenting
  /// network failures as missing data.
  static Map<String, String> calculateLocalHealthStats(
    List<Map<String, dynamic>> cycleLogs,
    Map<String, dynamic> profile,
  ) {
    if (cycleLogs.isEmpty) {
      return {
        'status': 'no_data',
        'averageCycleLength': 'No data logged yet',
        'averageBleedingDuration': 'No data logged yet',
        'sleepHours': 'No data logged yet',
        'recentStressLevel': 'No data logged yet',
      };
    }

    // Average cycle length: calculate from consecutive cycle starts if available, or profile
    String avgCycleLength = 'Not available';
    final dates = cycleLogs
        .map((l) => DateTime.tryParse(l['start_date']?.toString() ?? ''))
        .whereType<DateTime>()
        .toList()
      ..sort();

    if (dates.length >= 2) {
      int totalDays = 0;
      int intervals = 0;
      for (int i = 0; i < dates.length - 1; i++) {
        final diff = dates[i + 1].difference(dates[i]).inDays;
        if (diff >= 15 && diff <= 100) {
          totalDays += diff;
          intervals++;
        }
      }
      if (intervals > 0) {
        final avg = (totalDays / intervals).round();
        avgCycleLength = '$avg days';
      }
    }
    if (avgCycleLength == 'Not available' && profile['cycle_length'] != null) {
      avgCycleLength = '${profile['cycle_length']} days';
    }

    // Average bleeding duration: from profile or flow-logged records
    String avgBleeding = 'Not available';
    if (profile['period_duration'] != null) {
      avgBleeding = '${profile['period_duration']} days';
    } else {
      final bleedingCount = cycleLogs.where((l) {
        final flow = l['flow_intensity']?.toString().toLowerCase();
        return flow != null && flow.isNotEmpty && flow != 'none';
      }).length;
      if (bleedingCount > 0) {
        avgBleeding = '$bleedingCount logged days';
      }
    }

    // Average sleep hours:
    String avgSleep = 'Not available';
    final sleepList = cycleLogs
        .map((l) {
          final val = l['sleep_hours'];
          if (val is num && val.isFinite && !val.isNaN) {
            return val.toDouble();
          }
          if (val is String) {
            final trimmed = val.trim();
            if (trimmed.isNotEmpty) {
              final parsed = double.tryParse(trimmed);
              if (parsed != null && parsed.isFinite && !parsed.isNaN) {
                return parsed;
              }
            }
          }
          return null;
        })
        .whereType<double>()
        .toList();
    if (sleepList.isNotEmpty) {
      final avg = sleepList.reduce((a, b) => a + b) / sleepList.length;
      avgSleep = '${avg.toStringAsFixed(1)}h';
    }

    // Recent stress level:
    String recentStress = 'Not available';
    for (final l in cycleLogs) {
      if (l['stress_level'] != null) {
        recentStress = '${l['stress_level']} / 5';
        break;
      }
    }

    return {
      'status': 'available',
      'averageCycleLength': avgCycleLength,
      'averageBleedingDuration': avgBleeding,
      'sleepHours': avgSleep,
      'recentStressLevel': recentStress,
    };
  }

  /// Builds a formatted, paginated PDF health report document.
  ///
  /// - Profile maps are explicitly filtered to clinically relevant fields only.
  /// - Emergency contacts are excluded by default to safeguard third-party privacy.
  /// - AI summary is strictly opt-in and omitted entirely if unavailable.
  /// - Cycle history and symptoms are formatted into paginated tables.
  /// - Dashboard failure falls back gracefully to trustworthy local calculations.
  static Future<pw.Document> buildReportDocument({
    bool includeAiSummary = false,
    bool includeEmergencyContacts = false,
    AppLocalizations? l10n,
    AssistantService? assistantService,
    Dio? dio,
    DateTime? now,
  }) async {
    final reportDate = now ?? DateTime.now();
    final profile = LocalStorageService.getProfile() ?? {};
    final cycleLogs = LocalStorageService.getCycleLogs();
    final aggregatedSymptoms = aggregateSymptoms(cycleLogs);
    final localStats = calculateLocalHealthStats(cycleLogs, profile);

    Map<String, dynamic>? dashboard;
    bool dashboardFetchFailed = false;

    try {
      final client = dio ?? ApiClient.dio;
      final response = await client.get('/dashboard');
      if (response.data is Map) {
        dashboard = Map<String, dynamic>.from(response.data as Map);
      }
    } catch (_) {
      dashboardFetchFailed = true;
    }

    // AI Health Summary is strictly opt-in. Never call AssistantService unless user opted in.
    String? aiSummaryText;
    if (includeAiSummary) {
      try {
        final service = assistantService ?? AssistantService();
        final response = await service.chat(
          'Generate a short, factual health summary based on my recent cycle data.',
        );
        if (response.trim().isNotEmpty) {
          aiSummaryText = response.trim();
        }
      } catch (_) {
        // If the assistant call fails or is offline, omit the section completely.
        aiSummaryText = null;
      }
    }

    // Emergency contacts are excluded by default.
    List<Map<String, String>> emergencyContacts = [];
    if (includeEmergencyContacts) {
      emergencyContacts = LocalStorageService.getEmergencyContacts();
    }

    final pdf = pw.Document();

    pdf.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(32),
        build: (context) => [
          // Header
          pw.Header(
            level: 0,
            decoration: const pw.BoxDecoration(),
            child: pw.Row(
              mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
              crossAxisAlignment: pw.CrossAxisAlignment.end,
              children: [
                pw.Text(
                  'Rhythma Health Report',
                  style: pw.TextStyle(
                    fontSize: 22,
                    fontWeight: pw.FontWeight.bold,
                    color: PdfColors.purple900,
                  ),
                ),
                pw.Text(
                  'Generated: ${DateFormat.yMMMd().format(reportDate)}',
                  style: const pw.TextStyle(
                    fontSize: 10,
                    color: PdfColors.grey700,
                  ),
                ),
              ],
            ),
          ),
          pw.Divider(thickness: 1, color: PdfColors.purple200),
          pw.SizedBox(height: 12),

          // Patient Profile (strictly clinical fields only)
          pw.Text(
            'Patient Profile',
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold),
          ),
          pw.SizedBox(height: 6),
          pw.Container(
            padding: const pw.EdgeInsets.all(10),
            decoration: pw.BoxDecoration(
              border: pw.Border.all(color: PdfColors.grey300, width: 0.5),
              borderRadius: const pw.BorderRadius.all(pw.Radius.circular(4)),
            ),
            child: pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Row(
                  children: [
                    pw.Expanded(
                      child: _buildKeyValue(
                        'Name',
                        profile['name']?.toString() ?? 'Not specified',
                      ),
                    ),
                    pw.Expanded(
                      child: _buildKeyValue(
                        'Age',
                        profile['age'] != null
                            ? '${profile['age']} years'
                            : 'Not specified',
                      ),
                    ),
                  ],
                ),
                pw.SizedBox(height: 6),
                pw.Row(
                  children: [
                    pw.Expanded(
                      child: _buildKeyValue(
                        'Average Cycle Length',
                        profile['cycle_length'] != null
                            ? '${profile['cycle_length']} days'
                            : (localStats['averageCycleLength'] ?? 'Not specified'),
                      ),
                    ),
                    pw.Expanded(
                      child: _buildKeyValue(
                        'Period Duration',
                        profile['period_duration'] != null
                            ? '${profile['period_duration']} days'
                            : (localStats['averageBleedingDuration'] ?? 'Not specified'),
                      ),
                    ),
                  ],
                ),
                pw.SizedBox(height: 6),
                pw.Row(
                  children: [
                    pw.Expanded(
                      child: _buildKeyValue(
                        'Cycle Regularity',
                        profile['cycle_regular'] == true
                            ? 'Regular'
                            : (profile['cycle_regular'] == false
                                ? 'Irregular'
                                : 'Not specified'),
                      ),
                    ),
                    pw.Expanded(
                      child: _buildKeyValue(
                        'Last Period Start Date',
                        profile['last_period']?.toString() ?? 'Not specified',
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          pw.SizedBox(height: 16),

          // Health Metrics & Insights
          pw.Text(
            'Health Metrics & Insights',
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold),
          ),
          pw.SizedBox(height: 6),
          if (cycleLogs.isEmpty)
            pw.Text(
              'No cycle data logged yet',
              style: const pw.TextStyle(
                fontSize: 10,
                color: PdfColors.grey700,
                fontStyle: pw.FontStyle.italic,
              ),
            )
          else ...[
            pw.Container(
              padding: const pw.EdgeInsets.all(10),
              decoration: pw.BoxDecoration(
                border: pw.Border.all(color: PdfColors.grey300, width: 0.5),
                borderRadius: const pw.BorderRadius.all(pw.Radius.circular(4)),
              ),
              child: pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  pw.Row(
                    children: [
                      pw.Expanded(
                        child: _buildKeyValue(
                          'Avg Cycle Length',
                          dashboard?['insights']?['averageCycleLength'] != null
                              ? '${dashboard!['insights']['averageCycleLength']} days'
                              : localStats['averageCycleLength']!,
                        ),
                      ),
                      pw.Expanded(
                        child: _buildKeyValue(
                          'Avg Bleeding Duration',
                          dashboard?['insights']?['averageBleedingDuration'] != null
                              ? '${dashboard!['insights']['averageBleedingDuration']} days'
                              : localStats['averageBleedingDuration']!,
                        ),
                      ),
                    ],
                  ),
                  pw.SizedBox(height: 6),
                  pw.Row(
                    children: [
                      pw.Expanded(
                        child: _buildKeyValue(
                          'Average Sleep',
                          dashboard?['insights']?['sleepHours']?.toString() ??
                              localStats['sleepHours']!,
                        ),
                      ),
                      pw.Expanded(
                        child: _buildKeyValue(
                          'Recent Stress Level',
                          dashboard?['recentStressLevel'] != null
                              ? '${dashboard!['recentStressLevel']} / 5'
                              : localStats['recentStressLevel']!,
                        ),
                      ),
                    ],
                  ),
                  if (dashboardFetchFailed) ...[
                    pw.SizedBox(height: 4),
                    pw.Text(
                      'Note: Computed from on-device records (remote server metrics unavailable).',
                      style: const pw.TextStyle(
                        fontSize: 8,
                        color: PdfColors.grey600,
                        fontStyle: pw.FontStyle.italic,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
          pw.SizedBox(height: 16),

          // AI Health Summary (strictly opt-in, omitted when disabled or failed)
          if (includeAiSummary && aiSummaryText != null) ...[
            pw.Text(
              'AI Health Summary',
              style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold),
            ),
            pw.SizedBox(height: 2),
            pw.Text(
              'AI-generated text based on logged cycle patterns. Not clinical advice or a medical diagnosis.',
              style: const pw.TextStyle(
                fontSize: 8.5,
                color: PdfColors.grey700,
                fontStyle: pw.FontStyle.italic,
              ),
            ),
            pw.SizedBox(height: 6),
            pw.Container(
              padding: const pw.EdgeInsets.all(10),
              decoration: pw.BoxDecoration(
                color: PdfColors.grey100,
                border: pw.Border.all(color: PdfColors.grey300, width: 0.5),
                borderRadius: const pw.BorderRadius.all(pw.Radius.circular(4)),
              ),
              child: pw.Text(
                aiSummaryText,
                style: const pw.TextStyle(fontSize: 9.5, height: 1.3),
              ),
            ),
            pw.SizedBox(height: 16),
          ],

          // Symptom Frequency Table
          pw.Text(
            'Symptom Frequency',
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold),
          ),
          pw.SizedBox(height: 6),
          if (aggregatedSymptoms.isEmpty)
            pw.Text(
              'No symptoms logged yet',
              style: const pw.TextStyle(
                fontSize: 10,
                color: PdfColors.grey700,
                fontStyle: pw.FontStyle.italic,
              ),
            )
          else
            pw.Table.fromTextArray(
              headers: ['Symptom', 'Occurrences', 'Last Logged Date'],
              data: aggregatedSymptoms.map((item) {
                return [
                  item.symptom,
                  item.occurrences.toString(),
                  item.mostRecentDate.isNotEmpty ? item.mostRecentDate : '—',
                ];
              }).toList(),
              headerStyle: pw.TextStyle(
                fontWeight: pw.FontWeight.bold,
                fontSize: 9,
                color: PdfColors.purple900,
              ),
              headerDecoration: const pw.BoxDecoration(color: PdfColors.grey200),
              cellStyle: const pw.TextStyle(fontSize: 8.5),
              cellPadding:
                  const pw.EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              border: pw.TableBorder.all(color: PdfColors.grey300, width: 0.5),
            ),
          pw.SizedBox(height: 16),

          // Cycle History Table
          pw.Text(
            'Cycle History',
            style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold),
          ),
          pw.SizedBox(height: 6),
          if (cycleLogs.isEmpty)
            pw.Text(
              'No cycle history logged yet',
              style: const pw.TextStyle(
                fontSize: 10,
                color: PdfColors.grey700,
                fontStyle: pw.FontStyle.italic,
              ),
            )
          else
            pw.Table.fromTextArray(
              headers: [
                'Start Date',
                'Flow',
                'Symptoms',
                'Mood & Stress',
                'Sleep',
                'Notes',
              ],
              data: cycleLogs.map((log) {
                final symptomsRaw = log['symptoms'];
                String symptomsText = '—';
                if (symptomsRaw is List && symptomsRaw.isNotEmpty) {
                  symptomsText = symptomsRaw.join(', ');
                } else if (symptomsRaw is String && symptomsRaw.isNotEmpty) {
                  symptomsText = symptomsRaw;
                }

                String moodStress = '—';
                final mood = log['mood']?.toString();
                final stress = log['stress_level']?.toString();
                if (mood != null && stress != null) {
                  moodStress = '$mood / Stress $stress';
                } else if (mood != null) {
                  moodStress = mood;
                } else if (stress != null) {
                  moodStress = 'Stress: $stress';
                }

                final sleep = log['sleep_hours'] != null
                    ? '${log['sleep_hours']}h'
                    : '—';

                return [
                  log['start_date']?.toString() ?? '—',
                  log['flow_intensity']?.toString() ?? '—',
                  symptomsText,
                  moodStress,
                  sleep,
                  log['notes']?.toString() ?? '—',
                ];
              }).toList(),
              headerStyle: pw.TextStyle(
                fontWeight: pw.FontWeight.bold,
                fontSize: 9,
                color: PdfColors.purple900,
              ),
              headerDecoration: const pw.BoxDecoration(color: PdfColors.grey200),
              cellStyle: const pw.TextStyle(fontSize: 8),
              cellPadding:
                  const pw.EdgeInsets.symmetric(horizontal: 5, vertical: 4),
              border: pw.TableBorder.all(color: PdfColors.grey300, width: 0.5),
            ),

          // Optional Emergency Contacts (omitted by default)
          if (includeEmergencyContacts && emergencyContacts.isNotEmpty) ...[
            pw.SizedBox(height: 16),
            pw.Text(
              'Emergency Contacts',
              style: pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold),
            ),
            pw.SizedBox(height: 6),
            pw.Table.fromTextArray(
              headers: ['Name', 'Phone Number'],
              data: emergencyContacts
                  .map((c) => [c['name'] ?? '—', c['phone'] ?? '—'])
                  .toList(),
              headerStyle: pw.TextStyle(
                fontWeight: pw.FontWeight.bold,
                fontSize: 9,
                color: PdfColors.purple900,
              ),
              headerDecoration:
                  const pw.BoxDecoration(color: PdfColors.grey200),
              cellStyle: const pw.TextStyle(fontSize: 8.5),
              cellPadding:
                  const pw.EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              border: pw.TableBorder.all(color: PdfColors.grey300, width: 0.5),
            ),
          ],

          pw.SizedBox(height: 24),
          pw.Divider(thickness: 0.5, color: PdfColors.grey400),
          pw.SizedBox(height: 6),

          // Canonical medical disclaimer (from docs/health-disclaimers.md)
          pw.Text(
            'This report is an estimate based on self-logged data and is not a medical diagnosis. Please consult a qualified healthcare professional for medical advice.',
            style: const pw.TextStyle(fontSize: 8.5, color: PdfColors.grey700),
            textAlign: pw.TextAlign.center,
          ),
        ],
      ),
    );

    return pdf;
  }

  /// Builds raw PDF bytes for testability and sharing.
  static Future<Uint8List> buildReportPdfBytes({
    bool includeAiSummary = false,
    bool includeEmergencyContacts = false,
    AppLocalizations? l10n,
    AssistantService? assistantService,
    Dio? dio,
    DateTime? now,
  }) async {
    final pdf = await buildReportDocument(
      includeAiSummary: includeAiSummary,
      includeEmergencyContacts: includeEmergencyContacts,
      l10n: l10n,
      assistantService: assistantService,
      dio: dio,
      now: now,
    );
    return pdf.save();
  }

  /// Generates the PDF health report and opens the native share/print dialog.
  static Future<void> generateAndShareReport({
    bool includeAiSummary = false,
    bool includeEmergencyContacts = false,
    AppLocalizations? l10n,
    AssistantService? assistantService,
    Dio? dio,
  }) async {
    final bytes = await buildReportPdfBytes(
      includeAiSummary: includeAiSummary,
      includeEmergencyContacts: includeEmergencyContacts,
      l10n: l10n,
      assistantService: assistantService,
      dio: dio,
    );

    await Printing.sharePdf(
      bytes: bytes,
      filename: 'rhythma_health_report.pdf',
    );
  }

  static pw.Widget _buildKeyValue(String key, String value) {
    return pw.RichText(
      text: pw.TextSpan(
        children: [
          pw.TextSpan(
            text: '$key: ',
            style: pw.TextStyle(
              fontSize: 9,
              fontWeight: pw.FontWeight.bold,
              color: PdfColors.grey800,
            ),
          ),
          pw.TextSpan(
            text: value,
            style: const pw.TextStyle(
              fontSize: 9,
              color: PdfColors.grey900,
            ),
          ),
        ],
      ),
    );
  }
}
