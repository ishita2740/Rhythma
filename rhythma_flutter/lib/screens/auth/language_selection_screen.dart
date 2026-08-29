import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../providers/locale_provider.dart';
import '../../services/local_storage_service.dart';
import '../../config/supported_languages.dart';
import 'login_screen.dart';

class LanguageSelectionScreen extends StatefulWidget {
  const LanguageSelectionScreen({super.key});

  @override
  State<LanguageSelectionScreen> createState() =>
      _LanguageSelectionScreenState();
}

class _LanguageSelectionScreenState extends State<LanguageSelectionScreen> {
  String _selectedLanguage = 'en';

  @override
  void initState() {
    super.initState();
    _selectedLanguage = LocalStorageService.preferredLanguage;
  }

  Future<void> _onContinue() async {
    try {
      await LocalStorageService.setPreferredLanguage(_selectedLanguage);
      await LocalStorageService.setLanguageSelectionCompleted(true);
      if (!mounted) return;
      context.read<LocaleProvider>().setLocale(Locale(_selectedLanguage));
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    } catch (e) {
      if (!mounted) return;
      final l = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.languageSelectionError)),
      );
    }
  }
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: RhythmaColors.background,
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Image.asset(
                  'assets/images/logo.png',
                  height: 48,
                  fit: BoxFit.contain,
                ),
                const SizedBox(height: 12),
                Text(
                  l.onboardingStep1Title,
                  style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    color: RhythmaColors.foreground,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  l.onboardingStep1Subtitle,
                  style: TextStyle(
                    fontSize: 15,
                    color: RhythmaColors.mutedFg,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 32),
                ...List.generate(appSupportedLanguages.length, (i) {
                  final lang = appSupportedLanguages[i];
                  final selected = lang.code == _selectedLanguage;
                  return Semantics(
                    selected: selected,
                    label: lang.nativeName,
                    child: GestureDetector(
                      onTap: () {
                        setState(() => _selectedLanguage = lang.code);
                        context
                            .read<LocaleProvider>()
                            .setLocale(Locale(lang.code));
                      },
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 220),
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 20, vertical: 18),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(16),
                          color: selected
                              ? RhythmaColors.primary.withValues(alpha: 0.15)
                              : RhythmaColors.surface,
                          border: Border.all(
                            color: selected
                                ? RhythmaColors.primary
                                : Colors.transparent,
                            width: 2,
                          ),
                        ),
                        child: Row(
                          children: [
                            Text(
                              lang.nativeName,
                              style: TextStyle(
                                fontSize: 17,
                                fontWeight:
                                    selected ? FontWeight.bold : FontWeight.w500,
                                color: selected
                                    ? RhythmaColors.primary
                                    : RhythmaColors.foreground,
                              ),
                            ),
                            const Spacer(),
                            if (selected)
                              Icon(Icons.check_circle_rounded,
                                  color: RhythmaColors.primary),
                          ],
                        ),
                      ),
                    ),
                  );
                }),
                const SizedBox(height: 24),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    color: RhythmaColors.primary.withValues(alpha: 0.08),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('🔒', style: TextStyle(fontSize: 20)),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          l.onboardingPrivacyNote,
                          style: TextStyle(
                            fontSize: 13,
                            color: RhythmaColors.mutedFg,
                            height: 1.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 32),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _onContinue,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: RhythmaColors.primary,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                      elevation: 0,
                    ),
                    child: Text(
                      l.onboardingNext,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
