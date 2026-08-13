import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import '../config/theme.dart';
import '../services/local_storage_service.dart';

class BiometricAuthGate extends StatefulWidget {
  final Widget child;
  const BiometricAuthGate({super.key, required this.child});

  @override
  State<BiometricAuthGate> createState() => _BiometricAuthGateState();
}

class _BiometricAuthGateState extends State<BiometricAuthGate>
    with WidgetsBindingObserver {
  bool _locked = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (LocalStorageService.biometricEnabled) {
      _authenticate();
    } else {
      _locked = false;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed &&
        LocalStorageService.biometricEnabled) {
      _authenticate();
    }
  }

  Future<void> _authenticate() async {
    final auth = LocalAuthentication();
    final available =
        await auth.canCheckBiometrics || await auth.isDeviceSupported();
    if (!available) {
      if (mounted) setState(() => _locked = false);
      return;
    }
    try {
      final authenticated = await auth.authenticate(
        localizedReason: 'Authenticate to access Rhythma',
        options:
            const AuthenticationOptions(biometricOnly: false, stickyAuth: true),
      );
      if (mounted) setState(() => _locked = !authenticated);
    } catch (_) {
      if (mounted) setState(() => _locked = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_locked) return widget.child;
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.fingerprint, size: 64, color: RhythmaColors.primary),
            const SizedBox(height: 24),
            Text(
              'Authenticate to access Rhythma',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _authenticate,
              child: const Text('Unlock'),
            ),
          ],
        ),
      ),
    );
  }
}
