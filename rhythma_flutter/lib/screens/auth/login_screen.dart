import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:firebase_auth/firebase_auth.dart' hide User;
import 'package:rhythma/providers/profile_provider.dart';
import 'package:rhythma/providers/locale_provider.dart';
import 'package:rhythma/services/auth_service.dart';
import 'package:rhythma/l10n/app_localizations.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phoneController = TextEditingController();
  final _otpController = TextEditingController();
  
  bool _loading = false;
  bool _otpSent = false;
  String? _verificationId;

  @override
  void dispose() {
    _phoneController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  Future<void> _sendOtp() async {
    final l10n = AppLocalizations.of(context)!;
    String phone = _phoneController.text.trim();
    if (phone.isEmpty) {
      _showMessage(l10n.pleaseEnterPhoneNumber);
      return;
    }

    // Automatically format to E.164 (+91 for India) if they just entered 10 digits
    if (phone.length == 10 && !phone.startsWith('+')) {
      phone = '+91$phone';
    } else if (!phone.startsWith('+')) {
      _showMessage(l10n.pleaseEnterValidPhoneNumber);
      return;
    }

    setState(() => _loading = true);
    
    try {
      await FirebaseAuth.instance.verifyPhoneNumber(
        phoneNumber: phone,
        verificationCompleted: (PhoneAuthCredential credential) async {
          await _signInWithCredential(credential);
        },
        verificationFailed: (FirebaseAuthException e) {
          if (!mounted) return;
          setState(() => _loading = false);
          _showMessage(e.message ?? l10n.verificationFailed);
        },
        codeSent: (String verificationId, int? resendToken) {
          if (!mounted) return;
          setState(() {
            _loading = false;
            _otpSent = true;
            _verificationId = verificationId;
          });
          _showMessage(l10n.otpSentTo(phone));
        },
        codeAutoRetrievalTimeout: (String verificationId) {
          _verificationId = verificationId;
        },
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      _showMessage(e.toString());
    }
  }

  Future<void> _verifyOtp() async {
    final l10n = AppLocalizations.of(context)!;
    final otp = _otpController.text.trim();
    if (otp.isEmpty || _verificationId == null) {
      _showMessage(l10n.pleaseEnterOtp);
      return;
    }

    setState(() => _loading = true);

    try {
      final credential = PhoneAuthProvider.credential(
        verificationId: _verificationId!,
        smsCode: otp,
      );
      await _signInWithCredential(credential);
    } catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      _showMessage(l10n.invalidOtp);
    }
  }

  Future<void> _signInWithCredential(PhoneAuthCredential credential) async {
    final l10n = AppLocalizations.of(context)!;
    try {
      final userCredential = await FirebaseAuth.instance.signInWithCredential(credential);
      final idToken = await userCredential.user?.getIdToken();
      
      if (idToken == null) throw Exception(l10n.failedToGetIdToken);

      await AuthService().firebaseLogin(idToken);
      if (!mounted) return;

      context.read<ProfileProvider>().reloadProfile();
      final profile = context.read<ProfileProvider>().profile;
      final lang = profile['language'] as String?;
      if (lang != null) {
        context.read<LocaleProvider>().setLocale(Locale(lang));
      }

      Navigator.pushNamedAndRemoveUntil(context, '/home', (route) => false);
    } catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      _showMessage(e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Image.asset(
                  'assets/images/logo.png',
                  height: 120,
                  fit: BoxFit.contain,
                ),
                const SizedBox(height: 12),
                Text(
                  l10n.welcomeToRhythma,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 30, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(
                  _otpSent 
                    ? l10n.enterOtpSentToPhone
                    : l10n.loginOrSignUpWithPhone,
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Theme.of(context).hintColor),
                ),
                const SizedBox(height: 36),
                
                if (!_otpSent) ...[
                  TextField(
                    controller: _phoneController,
                    enabled: !_loading,
                    keyboardType: TextInputType.phone,
                    textInputAction: TextInputAction.next,
                    decoration: InputDecoration(
                      labelText: l10n.phoneNumber,
                      hintText: '+91 9876543210',
                      prefixIcon: const Icon(Icons.phone_outlined),
                      border: const OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton.icon(
                    onPressed: _loading ? null : _sendOtp,
                    icon: _loading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.send_rounded),
                    label: Text(_loading ? l10n.sendingOtp : l10n.getOtp),
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 50),
                    ),
                  ),
                ] else ...[
                  TextField(
                    controller: _otpController,
                    enabled: !_loading,
                    keyboardType: TextInputType.number,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _verifyOtp(),
                    decoration: InputDecoration(
                      labelText: l10n.otp,
                      hintText: '123456',
                      prefixIcon: const Icon(Icons.password_outlined),
                      border: const OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton.icon(
                    onPressed: _loading ? null : _verifyOtp,
                    icon: _loading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.login_rounded),
                    label: Text(_loading ? l10n.verifying : l10n.verifyOtp),
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 50),
                    ),
                  ),
                  TextButton(
                    onPressed: _loading ? null : () => setState(() => _otpSent = false),
                    child: Text(l10n.useDifferentPhoneNumber),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
