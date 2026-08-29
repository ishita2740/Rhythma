import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../providers/locale_provider.dart';
import '../../providers/profile_provider.dart';
import '../../components/shared.dart';
import '../../config/supported_languages.dart';

class LanguageScreen extends StatelessWidget {
  const LanguageScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final currentLocaleCode =
        context.watch<LocaleProvider>().locale.languageCode;

    return Container(
      decoration: BoxDecoration(gradient: RhythmaGradients.bg),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text(l10n.selectLanguage),
          centerTitle: true,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded),
            onPressed: () => Navigator.pop(context),
          ),
        ),
        body: ListView.builder(
          padding: const EdgeInsets.all(20),
          itemCount: appSupportedLanguages.length,
          itemBuilder: (context, index) {
            final lang = appSupportedLanguages[index];
            String langCode = lang.code;
            String langName = lang.nativeName;
            bool isSelected = currentLocaleCode == langCode;

            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: GlassCard(
                padding: EdgeInsets.zero,
                child: ListTile(
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                  title: Text(
                    langName,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight:
                          isSelected ? FontWeight.bold : FontWeight.normal,
                      color: isSelected
                          ? RhythmaColors.primary
                          : RhythmaColors.foreground,
                    ),
                  ),
                  trailing: isSelected
                      ? Icon(Icons.check_circle_rounded,
                          color: RhythmaColors.primary)
                      : null,
                  onTap: () {
                    context.read<LocaleProvider>().setLocale(Locale(langCode));
                    final profile = context.read<ProfileProvider>().profile;
                    if (profile.isNotEmpty) {
                      context.read<ProfileProvider>().mergeProfileWithSync({'language': langCode});
                    }
                  },
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}