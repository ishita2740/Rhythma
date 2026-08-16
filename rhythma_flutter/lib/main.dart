import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';

import 'components/biometric_auth_gate.dart';
import 'components/bottom_nav.dart';
import 'components/debug_data_indicator.dart';
import 'components/shared.dart';
import 'config/theme.dart';
import 'config/supported_languages.dart';

import 'providers/data_mode_provider.dart';
import 'providers/locale_provider.dart';
import 'providers/theme_provider.dart';
import 'providers/cycle_provider.dart';
import 'providers/profile_provider.dart';
import 'providers/sync_status_provider.dart';
import 'providers/dashboard_provider.dart';

import 'screens/assistant/assistant_screen.dart';
import 'screens/auth/language_selection_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/cycle/cycle_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/insights/insights_screen.dart';
import 'screens/onboarding/onboarding_screen.dart';
import 'screens/profile/profile_screen.dart';

import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'services/firestore_service.dart';
import 'services/local_storage_service.dart';
import 'services/notification_service.dart';
import 'services/offline_sync_service.dart';

final GlobalKey<NavigatorState> rootNavigatorKey = GlobalKey<NavigatorState>();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  await LocalStorageService.init();

  // Migration: existing users who completed onboarding already chose a language.
  // Mark language selection as completed so they are not shown the picker again.
  if (LocalStorageService.onboardingCompleted &&
      !LocalStorageService.languageSelectionCompleted) {
    await LocalStorageService.setLanguageSelectionCompleted(true);
  }

  await NotificationService.instance.init();
  await NotificationService.instance.scheduleAllAutomaticNotifications();
  await FirestoreService.init();
  await OfflineSyncService.init();

  ApiClient.init(onUnauthorized: () {
    final navigator = rootNavigatorKey.currentState;
    if (navigator == null) return;
    navigator.pushNamedAndRemoveUntil('/login', (route) => false);
  });

  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
    ),
  );

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => DataModeProvider()),
        ChangeNotifierProvider(create: (_) => LocaleProvider()),
        ChangeNotifierProvider(create: (_) => ThemeProvider()),
        ChangeNotifierProvider(create: (_) => CycleProvider()),
        ChangeNotifierProvider(create: (_) => ProfileProvider()),
        ChangeNotifierProvider(create: (_) => SyncStatusProvider()),
        ChangeNotifierProvider(create: (_) => DashboardProvider()),
      ],
      child: const RhythmaApp(),
    ),
  );
}

class RhythmaApp extends StatefulWidget {
  const RhythmaApp({super.key});

  @override
  State<RhythmaApp> createState() => _RhythmaAppState();
}

class _RhythmaAppState extends State<RhythmaApp> {
  // Created once, not inline in build(): a FutureBuilder whose `future` is
  // constructed fresh on every build restarts (goes back to `waiting`) on
  // every rebuild — and rebuilds happen for reasons unrelated to auth,
  // e.g. a locale or theme change calling notifyListeners(). That was
  // tearing down RhythmaRoot (and whatever onboarding page the user was
  // on) back to the splash screen, then to a brand new RhythmaRoot, every
  // time onboarding's language step changed the locale.
  late final Future<String?> _sessionFuture = AuthService().validateSession();

  @override
  Widget build(BuildContext context) {
    final themeProvider = context.watch<ThemeProvider>();

    return MaterialApp(
      navigatorKey: rootNavigatorKey,
      title: 'Rhythma',
      theme: RhythmaTheme.theme,
      themeMode: themeProvider.themeMode,
      debugShowCheckedModeBanner: false,
      locale: context.watch<LocaleProvider>().locale,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: appSupportedLanguages.map((l) => l.locale).toList(),
      home: FutureBuilder<String?>(
        // Confirms the stored token is still genuinely valid (not merely
        // present) via a lightweight /auth/me check, and scopes local
        // storage to the resulting account — see AuthService.validateSession.
        future: _sessionFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const SplashScreen();
          }
          if (snapshot.data != null) {
            return const BiometricAuthGate(child: RhythmaRoot());
          }
          if (!LocalStorageService.languageSelectionCompleted) {
            return const LanguageSelectionScreen();
          }
          return const LoginScreen();
        },
      ),
      routes: {
        '/login': (_) => const LoginScreen(),
        '/home': (_) => const RhythmaRoot(),
        '/assistant': (_) => const ShellBackground(child: AssistantScreen()),
      },
    );
  }
}

/// Root widget that decides whether to show onboarding or the main shell.
/// Uses a [ValueNotifier] so the onboarding screen can trigger a rebuild
/// without Navigator push/pop complexity.
class RhythmaRoot extends StatefulWidget {
  const RhythmaRoot({super.key});

  @override
  State<RhythmaRoot> createState() => _RhythmaRootState();
}

class _RhythmaRootState extends State<RhythmaRoot> {
  late bool _onboardingDone;

  @override
  void initState() {
    super.initState();
    _onboardingDone = LocalStorageService.onboardingCompleted;

    // Reload profile and sync locale after session validation completes
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context.read<ProfileProvider>().reloadProfile();
        final profile = context.read<ProfileProvider>().profile;
        final lang = profile['language'] as String?;
        if (lang != null) {
          context.read<LocaleProvider>().setLocale(Locale(lang));
        }
      }
    });
  }

  void _handleOnboardingComplete() {
    setState(() => _onboardingDone = true);
    context.read<ProfileProvider>().reloadProfile();
    final profile = context.read<ProfileProvider>().profile;
    final lang = profile['language'] as String?;
    if (lang != null) {
      context.read<LocaleProvider>().setLocale(Locale(lang));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_onboardingDone) {
      return OnboardingScreen(onComplete: _handleOnboardingComplete);
    }
    return const RhythmaShell();
  }
}

class RhythmaShell extends StatefulWidget {
  const RhythmaShell({super.key});

  @override
  State<RhythmaShell> createState() => _RhythmaShellState();
}

class _RhythmaShellState extends State<RhythmaShell> {
  int _currentIndex = 0;

  static const _screens = [
    HomeScreen(),
    CycleScreen(),
    AssistantScreen(),
    InsightsScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    context.watch<ThemeProvider>();
    return Container(
      decoration: BoxDecoration(
        gradient: RhythmaGradients.bg,
      ),
      child: Stack(
        children: [
          Scaffold(
            backgroundColor: Colors.transparent,
            extendBody: true,
            body: SafeArea(
              bottom: false,
              child: IndexedStack(
                index: _currentIndex,
                children: _screens,
              ),
            ),
            bottomNavigationBar: RhythmaBottomNav(
              currentIndex: _currentIndex,
              onTap: (i) => setState(() => _currentIndex = i),
            ),
          ),
          const DebugDataIndicator(),
        ],
      ),
    );
  }
}

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Image.asset(
              'assets/images/logo.png',
              height: 120,
              fit: BoxFit.contain,
            ),
            const SizedBox(height: 24),
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(
              'Rhythma',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Theme.of(context).primaryColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
