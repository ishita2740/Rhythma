import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/components/debug_data_indicator.dart';
import 'package:rhythma/config/app_config.dart';
import 'package:rhythma/providers/data_mode_provider.dart';

Widget createTestApp() {
  return MaterialApp(
    home: Scaffold(
      body: Stack(
        children: [
          const Placeholder(),
          ChangeNotifierProvider(
            create: (_) => DataModeProvider(),
            child: const DebugDataIndicator(),
          ),
        ],
      ),
    ),
  );
}

void main() {
  testWidgets('shows data mode banner in debug mode', (tester) async {
    await tester.pumpWidget(createTestApp());
    await tester.pumpAndSettle();

    // The indicator should display the label and API URL
    expect(find.textContaining('Live Data'), findsOneWidget);
    expect(find.textContaining(AppConfig.apiBaseUrl), findsWidgets);
  });

  testWidgets('shows cloud icon for live mode', (tester) async {
    await tester.pumpWidget(createTestApp());
    await tester.pumpAndSettle();

    // Live mode shows Icons.cloud_done
    expect(find.byIcon(Icons.cloud_done), findsOneWidget);
  });
}
