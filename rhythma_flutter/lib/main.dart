import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';

import 'components/bottom_nav.dart';
import 'components/shared.dart';
import 'config/theme.dart';

import 'providers/locale_provider.dart';
import 'providers/theme_provider.dart';
import 'providers/cycle_provider.dart';
import 'providers/profile_provider.dart';

import 'screens/assistant/assistant_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/auth/register_screen.dart';
import 'screens/cycle/cycle_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/insights/insights_screen.dart';
import 'screens/onboarding/onboarding_screen.dart';
import 'screens/profile/profile_screen.dart';

import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'services/local_storage_service.dart';
import 'services/notification_service.dart';

final GlobalKey<NavigatorState> rootNavigatorKey = GlobalKey<NavigatorState>();

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await LocalStorageService.init();
  await NotificationService.instance.init();

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
        ChangeNotifierProvider(create: (_) => LocaleProvider()),
        ChangeNotifierProvider(create: (_) => ThemeProvider()),
        ChangeNotifierProvider(create: (_) => CycleProvider()),
        ChangeNotifierProvider(create: (_) => ProfileProvider()),
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
  late Future<String?> _validationFuture;

  @override
  void initState() {
    super.initState();
    _validationFuture = AuthService().validateSession();
  }

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
      supportedLocales: const [
        Locale('en'),
        Locale('hi'),
        Locale('ta'),
        Locale('te'),
        Locale('mr'),
      ],
      home: FutureBuilder<String?>(
        // Confirms the stored token is still genuinely valid (not merely
        // present) via a lightweight /auth/me check, and scopes local
        // storage to the resulting account — see AuthService.validateSession.
        future: _validationFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const SplashScreen();
          }
          return snapshot.data != null ? const RhythmaRoot() : const LoginScreen();
        },
      ),
      routes: {
        '/login': (_) => const LoginScreen(),
        '/register': (_) => const RegisterScreen(),
        '/home': (_) => const RhythmaShell(),
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
  }

  void _handleOnboardingComplete() {
    setState(() => _onboardingDone = true);
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
      child: Scaffold(
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
            Icon(
              Icons.favorite,
              size: 80,
              color: Theme.of(context).primaryColor,
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