import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../components/shared.dart';
import '../../config/theme.dart';
import '../../services/auth_service.dart';
import '../../services/notification_service.dart';
import '../../providers/locale_provider.dart';
import '../../providers/theme_provider.dart';
import 'language_screen.dart';
import 'theme_screen.dart';
import '../sms/sms_screen.dart';
import 'package:url_launcher/url_launcher.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  // Notification Toggles
  bool _cycleTracking = true;
  bool _medicineAlerts = true;
  bool _wellnessTips = false;

  void _showLogoutDialog(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    showDialog(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.3),
      builder: (context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Material(
            color: Colors.transparent,
            child: GlassCard(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const TintedIcon(
                    icon: Icons.logout_rounded,
                    color: RhythmaColors.coral,
                    size: 48,
                  ),
                  const SizedBox(height: 18),
                  Text(
                    l10n.logOut,
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    l10n.logoutConfirmation,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: RhythmaColors.mutedFg,
                        ),
                  ),
                  const SizedBox(height: 24),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () => Navigator.pop(context),
                          style: OutlinedButton.styleFrom(
                            side: BorderSide(color: RhythmaColors.border),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                          child: Text(
                            l10n.cancel,
                            style: TextStyle(color: RhythmaColors.mutedFg),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: ElevatedButton(
                          onPressed: () async {
                            Navigator.pop(context); // Close dialog

                            // Clear the JWT token so the user is actually logged out.
                            //
                            // Intentional: we do NOT wipe local storage here.
                            // Profile info, cycle logs, chat history, and
                            // settings are stored on-device (see
                            // LocalStorageService) and are meant to persist
                            // across logins — wiping them on every logout was
                            // the cause of the profile resetting to its
                            // defaults each time (see PR history).
                            //
                            // Profile/chat-history/cycle-log data is now
                            // namespaced per account (LocalStorageService's
                            // currentUserId scoping), so a second person
                            // logging into a different account on this same
                            // device gets their own data, not the previous
                            // person's. AuthService.logout() clears the
                            // "which account is active" pointer below.
                            await AuthService().logout();

                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(l10n.loggedOutSuccess),
                                ),
                              );
                              // Clear the entire navigation stack and go back to
                              // the Login screen — a simple Navigator.pop only
                              // returned to the previous screen, leaving the
                              // user "logged in" in the UI even though nothing
                              // else about the session had changed.
                              Navigator.of(context, rootNavigator: true)
                                  .pushNamedAndRemoveUntil(
                                      '/login', (route) => false);
                            }
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: RhythmaColors.coral,
                            foregroundColor: Colors.white,
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                          child: Text(l10n.logOut),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<bool> _showConfirmationDialog(
      String title, String content, bool newValue) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title, style: TextStyle(color: RhythmaColors.primary)),
        content: Text(
          newValue
              ? 'Are you sure you want to turn ON $content?'
              : 'Are you sure you want to turn OFF $content?',
        ),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: RhythmaColors.primary,
              foregroundColor: RhythmaColors.primaryFg,
            ),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
    return result ?? false;
  }

  @override
  Widget build(BuildContext context) {
    context.watch<ThemeProvider>();
    final l10n = AppLocalizations.of(context)!;
    final currentLocaleCode =
        context.watch<LocaleProvider>().locale.languageCode;
    String currentLanguageName = LanguageScreen.languages.entries
        .firstWhere((entry) => entry.value == currentLocaleCode,
            orElse: () => const MapEntry('English', 'en'))
        .key;

    return Container(
      decoration: BoxDecoration(gradient: RhythmaGradients.bg),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text(l10n.settingsTitle),
          centerTitle: true,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded),
            onPressed: () => Navigator.pop(context),
          ),
        ),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            // App Preferences Section
            SectionHeader(title: l10n.appPreferences),
            GlassCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: [
                  ListTile(
                    leading: TintedIcon(
                      icon: Icons.language_rounded,
                      color: RhythmaColors.primary,
                      size: 36,
                    ),
                    title: Text(l10n.languagePreferences),
                    subtitle: Text(currentLanguageName),
                    trailing: Icon(Icons.chevron_right_rounded,
                        color: RhythmaColors.mutedFg),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                            builder: (context) => const LanguageScreen()),
                      );
                    },
                  ),
                  Divider(height: 1, color: RhythmaColors.border),
                  ListTile(
                    leading: TintedIcon(
                      icon: Icons.palette_rounded,
                      color: RhythmaColors.primary,
                      size: 36,
                    ),
                    title: Text(l10n.themeToggle),
                    trailing: Icon(Icons.chevron_right_rounded,
                        color: RhythmaColors.mutedFg),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                            builder: (context) => const ThemeScreen()),
                      );
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Notifications Section
            SectionHeader(title: l10n.notificationsTitle),
            GlassCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: [
                  SwitchListTile(
                    secondary: const TintedIcon(
                      icon: Icons.calendar_month_rounded,
                      color: RhythmaColors.rose,
                      size: 36,
                    ),
                    title: Text(l10n.cycleTrackingReminders),
                    value: _cycleTracking,
                    activeThumbColor: RhythmaColors.primary,
                    onChanged: (bool value) async {
                      bool confirm = await _showConfirmationDialog(
                          'Cycle Tracking', 'cycle tracking reminders', value);
                      if (confirm) {
                        setState(() {
                          _cycleTracking = value;
                        });
                      }
                    },
                  ),
                  Divider(height: 1, color: RhythmaColors.border),
                  SwitchListTile(
                    secondary: const TintedIcon(
                      icon: Icons.medication_rounded,
                      color: RhythmaColors.teal,
                      size: 36,
                    ),
                    title: Text(l10n.medicineAlerts),
                    value: _medicineAlerts,
                    activeThumbColor: RhythmaColors.primary,
                    onChanged: (bool value) async {
                      bool confirm = await _showConfirmationDialog(
                          'Medicine Alerts', 'medicine alerts', value);
                      if (!confirm) return;

                      setState(() {
                        _medicineAlerts = value;
                      });
                      if (value) {
                        // Request permissions first
                        bool granted = await NotificationService.instance
                            .requestPermissions();
                        if (granted) {
                          // Schedule a test medicine alert for 10 seconds from now
                          NotificationService.instance.scheduleMedicineAlert(
                            id: 1001,
                            title: 'Medicine Reminder',
                            body: 'Time to take your iron supplement!',
                            scheduledDate:
                                DateTime.now().add(const Duration(seconds: 10)),
                          );
                        } else {
                          // Revert if denied
                          setState(() {
                            _medicineAlerts = false;
                          });
                        }
                      } else {
                        NotificationService.instance.cancelNotification(1001);
                      }
                    },
                  ),
                  Divider(height: 1, color: RhythmaColors.border),
                  SwitchListTile(
                    secondary: const TintedIcon(
                      icon: Icons.spa_rounded,
                      color: RhythmaColors.coral,
                      size: 36,
                    ),
                    title: Text(l10n.wellnessTips),
                    value: _wellnessTips,
                    activeThumbColor: RhythmaColors.primary,
                    onChanged: (bool value) async {
                      bool confirm = await _showConfirmationDialog(
                          'Wellness Tips', 'wellness tips', value);
                      if (confirm) {
                        setState(() {
                          _wellnessTips = value;
                        });
                      }
                    },
                  ),
                  Divider(height: 1, color: RhythmaColors.border),
                  ListTile(
                    leading: TintedIcon(
                      icon: Icons.notifications_active_rounded,
                      color: RhythmaColors.primary,
                      size: 36,
                    ),
                    title: const Text('Test Notification Now'),
                    subtitle: const Text('Sends an instant alert'),
                    trailing:
                        Icon(Icons.send_rounded, color: RhythmaColors.mutedFg),
                    onTap: () async {
                      bool granted = await NotificationService.instance
                          .requestPermissions();
                      if (granted) {
                        NotificationService.instance.showInstantNotification(
                          id: 9999,
                          title: 'Rhythma Test',
                          body: 'Native notifications are working perfectly!',
                        );
                      }
                    },
                  ),
                  Divider(height: 1, color: RhythmaColors.border),
                  ListTile(
                    leading: TintedIcon(
                      icon: Icons.sms_rounded,
                      color: RhythmaColors.teal,
                      size: 36,
                    ),
                    title: const Text('SMS Cycle Summaries'),
                    subtitle: const Text('Get a text summary sent to your phone'),
                    trailing: Icon(Icons.chevron_right_rounded, color: RhythmaColors.mutedFg),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(builder: (context) => const SmsScreen()),
                      );
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Security & Privacy Section
            SectionHeader(title: l10n.securityPrivacyTitle),
            GlassCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: [
                  ListTile(
                    leading: TintedIcon(
                      icon: Icons.security_rounded,
                      color: RhythmaColors.mutedFg,
                      size: 36,
                    ),
                    title: Text(l10n.appPermissions),
                    trailing: Icon(Icons.chevron_right_rounded,
                        color: RhythmaColors.mutedFg),
                    onTap: () {
                      showDialog(
                        context: context,
                        builder: (context) => AlertDialog(
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(20),
                          ),
                          title: Text(
                            'Coming Soon',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: RhythmaColors.primary),
                          ),
                          content: const Text(
                            'This feature is currently under development.',
                            textAlign: TextAlign.center,
                          ),
                          actionsAlignment: MainAxisAlignment.center,
                          actions: [
                            ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: RhythmaColors.primary,
                                foregroundColor: RhythmaColors.primaryFg,
                              ),
                              onPressed: () => Navigator.pop(context),
                              child: const Text('OK'),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                  Divider(height: 1, color: RhythmaColors.border),
                  ListTile(
                    leading: TintedIcon(
                      icon: Icons.privacy_tip_rounded,
                      color: RhythmaColors.mutedFg,
                      size: 36,
                    ),
                    title: Text(l10n.privacyPolicy),
                    trailing: Icon(Icons.chevron_right_rounded,
                        color: RhythmaColors.mutedFg),
                    onTap: () {
                      showDialog(
                        context: context,
                        builder: (context) => AlertDialog(
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(20),
                          ),
                          title: Text(
                            'Coming Soon',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: RhythmaColors.primary),
                          ),
                          content: const Text(
                            'This feature is currently under development.',
                            textAlign: TextAlign.center,
                          ),
                          actionsAlignment: MainAxisAlignment.center,
                          actions: [
                            ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: RhythmaColors.primary,
                                foregroundColor: RhythmaColors.primaryFg,
                              ),
                              onPressed: () => Navigator.pop(context),
                              child: const Text('OK'),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Help & Support Section
            SectionHeader(title: l10n.settingsHelpSupport),
            GlassCard(
              padding: EdgeInsets.zero,
              child: ListTile(
                leading: const TintedIcon(
                  icon: Icons.support_agent_rounded,
                  color: RhythmaColors.teal,
                  size: 36,
                ),
                title: Text(l10n.settingsContactUs),
                subtitle: Text(l10n.settingsContactDesc),
                trailing: Icon(Icons.chevron_right_rounded,
                    color: RhythmaColors.mutedFg),
                onTap: () async {
                  final Uri emailUri = Uri(
                    scheme: 'mailto',
                    path: 'support@rhythma.com',
                    query:
                        'subject=Rhythma Support & Bug Report&body=Hi Rhythma Team,%0D%0A%0D%0AI need help with...', // %0D%0A is for line breaks
                  );

                  if (await canLaunchUrl(emailUri)) {
                    await launchUrl(emailUri,
                        mode: LaunchMode.externalApplication);
                  } else {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text(l10n.settingsEmailError)),
                      );
                    }
                  }
                },
              ),
            ),
            const SizedBox(height: 24),

            GlassCard(
              padding: EdgeInsets.zero,
              child: ListTile(
                leading: const TintedIcon(
                  icon: Icons.logout_rounded,
                  color: RhythmaColors.coral,
                  size: 36,
                ),
                title: Text(
                  l10n.logOut,
                  style: const TextStyle(
                    color: RhythmaColors.coral,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                trailing: Icon(Icons.chevron_right_rounded,
                    color: RhythmaColors.mutedFg),
                onTap: () => _showLogoutDialog(context),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }
}
