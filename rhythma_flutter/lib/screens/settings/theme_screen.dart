import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../providers/theme_provider.dart';
import '../../components/shared.dart';

class ThemeScreen extends StatelessWidget {
  const ThemeScreen({super.key});

  static const List<Map<String, dynamic>> predefinedColors = [
    {'name': 'Lavender', 'color': Color(0xFF9B72CF)},
    {'name': 'Rose Pink', 'color': Color(0xFFE07AAD)},
    {'name': 'Ocean Teal', 'color': Color(0xFF52B3B0)},
    {'name': 'Mint Green', 'color': Color(0xFF6EB582)},
    {'name': 'Warm Coral', 'color': Color(0xFFE8946A)},
    {'name': 'Sky Blue', 'color': Color(0xFF6A98E8)},
    {'name': 'Sunset Yellow', 'color': Color(0xFFE8C46A)},
    {'name': 'Berry Purple', 'color': Color(0xFFB3528A)},
  ];

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final themeProvider = context.watch<ThemeProvider>();

    return Container(
      decoration: BoxDecoration(gradient: RhythmaGradients.bg),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text(
              l10n.themeToggle), // Reusing existing localized string for title
          centerTitle: true,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded),
            onPressed: () => Navigator.pop(context),
          ),
        ),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            SectionHeader(title: l10n.darkMode),
            GlassCard(
              padding: EdgeInsets.zero,
              child: SwitchListTile(
                secondary: TintedIcon(
                  icon: Icons.dark_mode_rounded,
                  color: RhythmaColors.primary,
                  size: 36,
                ),
                title: Text(l10n.darkMode),
                value: themeProvider.isDarkMode,
                activeThumbColor: RhythmaColors.primary,
                onChanged: (bool value) {
                  themeProvider.setDarkMode(value);
                },
              ),
            ),
            const SizedBox(height: 24),
            const SectionHeader(
                title: 'Theme Color'), // Ideally localized later
            GlassCard(
              padding: const EdgeInsets.all(20),
              child: Wrap(
                spacing: 20,
                runSpacing: 20,
                alignment: WrapAlignment.center,
                children: predefinedColors.map((item) {
                  final color = item['color'] as Color;
                  final isSelected =
                      themeProvider.primaryColor.value == color.value;

                  return GestureDetector(
                    onTap: () {
                      themeProvider.setPrimaryColor(color);
                    },
                    child: Container(
                      width: 50,
                      height: 50,
                      decoration: BoxDecoration(
                        color: color,
                        shape: BoxShape.circle,
                        border: isSelected
                            ? Border.all(
                                color: RhythmaColors.foreground, width: 3)
                            : null,
                        boxShadow: [
                          BoxShadow(
                            color: color.withOpacity(0.4),
                            blurRadius: 8,
                            offset: const Offset(0, 4),
                          )
                        ],
                      ),
                      child: isSelected
                          ? const Icon(Icons.check, color: Colors.white)
                          : null,
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
