import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:rhythma/services/local_storage_service.dart';
import 'package:rhythma/services/api_client.dart';
import 'package:rhythma/services/assistant_service.dart';

class ReportService {
  static Future<void> generateAndShareReport() async {
    final profile = LocalStorageService.getProfile() ?? {};
    final contacts = LocalStorageService.getEmergencyContacts();
    final cycleLogs = LocalStorageService.getCycleLogs();
    final reportDate = DateTime.now();
    final symptoms = cycleLogs.expand((log) => log['symptoms'] ?? []).toList();

    Map<String, dynamic> dashboard = {};

    try {
      final response = await ApiClient.dio.get('/dashboard');
      dashboard = Map<String, dynamic>.from(response.data);
    } catch (_) {}

    String aiSummary = 'No AI summary available';

    try {
      final assistant = AssistantService();
      aiSummary = await assistant.chat(
        'Generate a short health summary based on my recent cycle data.',
      );
    } catch (_) {}

    final history = dashboard['cycleHistory'] as List? ?? [];
    final cycleLengthTrend = history
        .map((e) => (e as Map)['cycle_length'])
        .whereType<num>()
        .map((n) => n.toInt())
        .toList();

    int variability = 0;
    if (cycleLengthTrend.length >= 2) {
      final mean = cycleLengthTrend.reduce((a, b) => a + b) / cycleLengthTrend.length;
      final variance = cycleLengthTrend.map((v) => (v - mean) * (v - mean)).reduce((a, b) => a + b) / cycleLengthTrend.length;
      variability = variance <= 0 ? 0 : variance.round();
    }
    final isStable = variability <= 3;
    final consistencyDesc = cycleLengthTrend.length >= 2
        ? (isStable ? 'Stable (Variability: $variability days)' : 'Moderate Variability ($variability days)')
        : 'Not enough data for trend';

    final pdf = pw.Document();

    pdf.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        build: (context) => [
          pw.Header(
            level: 0,
            child: pw.Text(
              'Rhythma Health Report',
              style: pw.TextStyle(
                fontSize: 24,
                fontWeight: pw.FontWeight.bold,
              ),
            ),
          ),
          pw.SizedBox(height: 10),
          pw.Text(
            'Generated on: ${reportDate.day}/${reportDate.month}/${reportDate.year}',
          ),
          pw.Text('Profile'),
          pw.Text(profile.toString()),
          pw.SizedBox(height: 20),
          pw.Text('Cycle Logs'),
          pw.Text(cycleLogs.toString()),
          pw.SizedBox(height: 20),
          pw.Text('Emergency Contacts'),
          pw.Text(contacts.toString()),
          pw.SizedBox(height: 20),
          pw.Text(
            'Cycle History',
            style: pw.TextStyle(
              fontWeight: pw.FontWeight.bold,
              fontSize: 16,
            ),
          ),
          pw.SizedBox(height: 10),
          if (cycleLogs.isEmpty)
            pw.Text('No cycle history available')
          else
            ...cycleLogs.map(
              (log) => pw.Text(log.toString()),
            ),
          pw.Text(
            'Symptoms',
            style: pw.TextStyle(
              fontWeight: pw.FontWeight.bold,
              fontSize: 16,
            ),
          ),
          pw.SizedBox(height: 10),
          if (symptoms.isEmpty)
            pw.Text('No symptoms logged')
          else
            ...symptoms.map(
              (symptom) => pw.Text('- $symptom'),
            ),
          pw.SizedBox(height: 20),
          pw.Text(
            'AI Health Summary',
            style: pw.TextStyle(
              fontWeight: pw.FontWeight.bold,
              fontSize: 16,
            ),
          ),
          pw.SizedBox(height: 10),
          pw.Text(aiSummary),
          pw.SizedBox(height: 20),
          pw.Text(
            'Health Insights',
            style: pw.TextStyle(
              fontWeight: pw.FontWeight.bold,
              fontSize: 16,
            ),
          ),
          pw.SizedBox(height: 10),
          pw.Text(
            'Avg Cycle Length: ${dashboard['insights']?['averageCycleLength'] ?? 'N/A'} days',
          ),
          pw.Text(
            'Shortest Cycle: ${dashboard['insights']?['shortestCycleLength'] ?? 'N/A'} days',
          ),
          pw.Text(
            'Longest Cycle: ${dashboard['insights']?['longestCycleLength'] ?? 'N/A'} days',
          ),
          pw.Text(
            'Avg Bleeding Duration: ${dashboard['insights']?['averageBleedingDuration'] ?? 'N/A'} days',
          ),
          pw.Text(
            'Cycle Consistency: $consistencyDesc',
          ),
          pw.Text(
            'Sleep Hours: ${dashboard['insights']?['sleepHours'] ?? 'N/A'}',
          ),
          pw.Text(
            'Recent Stress Level: ${dashboard['recentStressLevel'] ?? 'N/A'}',
          ),
          pw.SizedBox(height: 24),
          pw.Divider(),
          pw.SizedBox(height: 8),
          pw.Text(
            'This report is an estimate based on self-logged data and is not a medical diagnosis. Please consult a qualified healthcare professional for medical advice.',
            style: pw.TextStyle(fontSize: 9, color: PdfColors.grey700),
          ),
        ],
      ),
    );

    final bytes = await pdf.save();

    await Printing.sharePdf(
      bytes: bytes,
      filename: 'rhythma_health_report.pdf',
    );
  }
}
