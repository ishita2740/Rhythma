import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../components/shared.dart';
import '../../services/sms_service.dart';

/// SMS Health Summary screen.
/// Users configure a phone number to receive summaries via SMS, useful in
/// low-data areas, and can trigger an on-demand summary right now.
class SmsScreen extends StatefulWidget {
  const SmsScreen({super.key});

  @override
  State<SmsScreen> createState() => _SmsScreenState();
}

class _SmsScreenState extends State<SmsScreen> {
  final _sms = SmsService();
  final _phoneCtrl = TextEditingController();
  bool _smsEnabled = false;
  bool _saving = false;
  bool _sending = false;
  bool _loading = true;
  String _loadError = '';
  bool _initialized = false;

  // E.164: a leading '+', then 1-15 digits, first digit 1-9. This is a
  // basic client-side check to catch obvious typos before hitting the
  // backend — the backend remains the source of truth for validation.
  static final _e164 = RegExp(r'^\+[1-9]\d{1,14}$');

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      _initialized = true;
      _loadSettings();
    }
  }

  @override
  void dispose() {
    _phoneCtrl.dispose();
    super.dispose();
  }

  // The phone number here is loaded from /sms/settings, which is where
  // this feature's phone number actually lives on the backend — there is
  // no separate "profile" endpoint with a phone field to load from
  // instead. This is intentional, not a placeholder: it's the same
  // number the user set up for weekly summaries, reused here so the Send
  // action doesn't need its own manual-entry field.
  Future<void> _loadSettings() async {
    final l10n = AppLocalizations.of(context)!;
    setState(() {
      _loading = true;
      _loadError = '';
    });
    try {
      final settings = await _sms.getSettings();
      setState(() {
        _phoneCtrl.text = (settings['phoneNumber'] as String?) ?? '';
        _smsEnabled = settings['enabled'] as bool? ?? false;
      });
    } on DioException catch (e) {
      // A 404 here just means the user has no saved settings yet, which
      // is a normal first-run state, not an error to surface. Anything
      // else (network failure, auth failure, server error) is a real
      // problem and should be shown, not swallowed silently.
      if (e.response?.statusCode != 404) {
        setState(() => _loadError = _friendlyError(e, l10n));
      }
    } catch (e) {
      setState(() => _loadError = l10n.smsErrorGeneric);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _saveSettings() async {
    final l10n = AppLocalizations.of(context)!;
    final phone = _phoneCtrl.text.trim();
    if (_smsEnabled && phone.isEmpty) {
      _showSnack(l10n.smsErrorEnterPhone, isError: true);
      return;
    }
    if (phone.isNotEmpty && !_e164.hasMatch(phone)) {
      _showSnack(l10n.smsErrorInvalidPhone, isError: true);
      return;
    }

    setState(() => _saving = true);
    try {
      await _sms.saveSettings(phoneNumber: phone, enabled: _smsEnabled);
      _showSnack(l10n.smsSuccessSaved);
    } catch (e) {
      _showSnack(_friendlyError(e, l10n), isError: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _sendSummaryNow() async {
    final l10n = AppLocalizations.of(context)!;
    final phone = _phoneCtrl.text.trim();
    if (phone.isEmpty) {
      _showSnack(l10n.smsErrorAddPhoneFirst, isError: true);
      return;
    }
    if (!_e164.hasMatch(phone)) {
      _showSnack(l10n.smsErrorInvalidPhone, isError: true);
      return;
    }

    setState(() => _sending = true);
    try {
      await _sms.sendSummary(phoneNumber: phone, message: l10n.smsSummaryMessage);
      _showSnack(l10n.smsSuccessSent);
    } catch (e) {
      _showSnack(_friendlyError(e, l10n), isError: true);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  /// Covers the feedback cases issue #26 asks for: success (handled at the
  /// call sites above), network failures, authentication failures, and
  /// backend rate limiting, falling back to the backend's own error detail
  /// (e.g. an invalid phone format, or a Twilio-side error) when it's none
  /// of those.
  String _friendlyError(Object e, AppLocalizations l10n) {
    if (e is DioException) {
      final status = e.response?.statusCode;
      if (status == 429) {
        return l10n.smsErrorRateLimit;
      }
      if (status == 401) {
        return l10n.smsErrorSessionExpired;
      }
      final data = e.response?.data;
      if (data is Map && data['detail'] is String && (data['detail'] as String).isNotEmpty) {
        return data['detail'] as String;
      }
      if (e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.unknown) {
        return l10n.smsErrorNetwork;
      }
      return l10n.smsErrorGeneric;
    }
    return l10n.smsErrorGeneric;
  }

  void _showSnack(String text, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(text),
        backgroundColor: isError ? Colors.red : RhythmaColors.teal,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final hasPhone = _phoneCtrl.text.trim().isNotEmpty;

    // Matches the same Container(gradient) + Scaffold(transparent) + AppBar
    // wrapper every other pushed settings sub-screen uses (see
    // theme_screen.dart / language_screen.dart). Without it, this screen
    // rendered on a bare black canvas with no back button and no Material
    // text styling, since it was built to be a tab body, not a pushed route.
    return Container(
      decoration: BoxDecoration(gradient: RhythmaGradients.bg),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text(l10n.smsScreenTitle),
          centerTitle: true,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded),
            onPressed: () => Navigator.pop(context),
          ),
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _loadSettings,
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 100),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(l10n.smsScreenSubtitle,
                          style: TextStyle(fontSize: 13, color: RhythmaColors.mutedFg)),
                      const SizedBox(height: 20),

                      if (_loadError.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 14),
                          child: GlassCard(
                            child: Row(
                              children: [
                                Icon(Icons.error_outline, color: RhythmaColors.rose, size: 20),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    _loadError,
                                    style: TextStyle(color: RhythmaColors.mutedFg, fontSize: 12),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),

                      // Info card
                      GlassCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                TintedIcon(icon: Icons.sms_rounded, color: RhythmaColors.teal),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(l10n.smsInfoCardTitle,
                                      style: TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.w600,
                                          color: RhythmaColors.foreground)),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            Text(
                              l10n.smsInfoCardBody,
                              style: TextStyle(
                                  fontSize: 13, color: RhythmaColors.mutedFg, height: 1.5),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 16),

                      // Config card
                      GlassCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(l10n.smsConfigTitle,
                                style: TextStyle(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w600,
                                    color: RhythmaColors.foreground)),
                            const SizedBox(height: 16),
                            TextField(
                              controller: _phoneCtrl,
                              keyboardType: TextInputType.phone,
                              onChanged: (_) => setState(() {}),
                              decoration: InputDecoration(
                                labelText: l10n.smsPhoneLabel,
                                hintText: l10n.smsPhoneHint,
                                prefixIcon: const Icon(Icons.phone_rounded),
                              ),
                            ),
                            const SizedBox(height: 16),
                            Row(
                              children: [
                                Expanded(
                                  child: Text(l10n.smsEnableWeekly,
                                      style: TextStyle(
                                          fontSize: 14, color: RhythmaColors.foreground)),
                                ),
                                Switch(
                                  value: _smsEnabled,
                                  onChanged: (v) => setState(() => _smsEnabled = v),
                                  activeThumbColor: RhythmaColors.primary,
                                  activeTrackColor: RhythmaColors.primary.withValues(alpha: 0.5),
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton(
                                onPressed: _saving ? null : _saveSettings,
                                child: _saving
                                    ? const SizedBox(
                                        width: 18,
                                        height: 18,
                                        child: CircularProgressIndicator(
                                            strokeWidth: 2, color: Colors.white))
                                    : Text(l10n.smsSaveSettings),
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 12),

                      // On-demand summary, a real action wired to the backend,
                      // replacing the previous static "Sample SMS" placeholder.
                      GlassCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(l10n.smsSendSectionTitle,
                                style: TextStyle(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w600,
                                    color: RhythmaColors.foreground)),
                            const SizedBox(height: 4),
                            if (hasPhone) ...[
                              Text(
                                l10n.smsSendRecipientPrefix,
                                style: TextStyle(fontSize: 12, color: RhythmaColors.mutedFg),
                              ),
                              Text(
                                _phoneCtrl.text.trim(),
                                style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: RhythmaColors.foreground),
                              ),
                            ] else
                              Text(
                                l10n.smsSendNoPhone,
                                style: TextStyle(fontSize: 12, color: RhythmaColors.mutedFg),
                              ),
                            const SizedBox(height: 10),
                            Container(
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: RhythmaColors.surfaceMuted,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                l10n.smsSummaryMessage,
                                style: TextStyle(
                                    fontSize: 13,
                                    color: RhythmaColors.foreground,
                                    height: 1.6,
                                    fontFamily: 'monospace'),
                              ),
                            ),
                            const SizedBox(height: 16),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton(
                                onPressed: (_sending || !hasPhone) ? null : _sendSummaryNow,
                                child: _sending
                                    ? const SizedBox(
                                        width: 18,
                                        height: 18,
                                        child: CircularProgressIndicator(
                                            strokeWidth: 2, color: Colors.white))
                                    : Text(l10n.smsSendButton),
                              ),
                            ),
                          ],
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