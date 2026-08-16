import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/data_mode_provider.dart';

/// A small banner visible only in debug builds that indicates the active
/// data source (live vs dev) and the configured API endpoint.
///
/// This widget does nothing in profile/release builds.
class DebugDataIndicator extends StatelessWidget {
  const DebugDataIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    if (!kDebugMode) return const SizedBox.shrink();

    final provider = context.watch<DataModeProvider>();
    final Color bgColor = provider.isLive ? Colors.green : Colors.orange;
    final String label = provider.label;
    final String url = provider.apiUrl;

    return Positioned(
      left: 0,
      right: 0,
      bottom: 0,
      child: MaterialBanner(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        backgroundColor: bgColor.withOpacity(0.85),
        leading: Icon(
          provider.isLive ? Icons.cloud_done : Icons.cloud_outlined,
          size: 16,
          color: Colors.white,
        ),
        content: Text(
          '$label  ·  $url',
          style: const TextStyle(fontSize: 11, color: Colors.white),
        ),
        actions: const [SizedBox.shrink()],
      ),
    );
  }
}
