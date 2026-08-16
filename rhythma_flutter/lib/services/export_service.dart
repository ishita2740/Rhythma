import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:rhythma/services/local_storage_service.dart';

class ExportService {
  /// Returns the export data as a pretty-printed JSON string.
  static String buildExportJson() {
    final data = _buildExportData();
    return const JsonEncoder.withIndent('  ').convert(data);
  }

  /// Gathers the user's profile and emergency contacts into a JSON string.
  static Map<String, dynamic> _buildExportData() {
    final profile = LocalStorageService.getProfile() ?? {};
    final contacts = LocalStorageService.getEmergencyContacts();
    final cycleLogs = LocalStorageService.getCycleLogs();

    return {
      'export_date': DateTime.now().toIso8601String(),
      'profile': profile,
      'emergency_contacts': contacts,
      'cycle_logs': cycleLogs,
    };
  }

  /// Exports the user's data as a JSON file and opens the native share sheet.
  static Future<void> exportAndShare() async {
    final data = _buildExportData();
    final jsonString =
        const JsonEncoder.withIndent('  ').convert(data);

    final directory = await getTemporaryDirectory();
    final timestamp = DateTime.now().millisecondsSinceEpoch;
    final file = File('${directory.path}/rhythma_export_$timestamp.json');
    await file.writeAsString(jsonString);

    try {
      await Share.shareXFiles(
        [XFile(file.path)],
        subject: 'Rhythma Data Export',
      );
    } catch (_) {
      // Fallback for desktop platforms or environments without native share handlers
    } finally {
      if (await file.exists()) {
        try {
          await file.delete();
        } catch (_) {}
      }
    }
  }
}
