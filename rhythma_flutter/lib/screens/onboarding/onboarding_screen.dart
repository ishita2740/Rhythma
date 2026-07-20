import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../providers/locale_provider.dart';
import '../../services/local_storage_service.dart';
import '../../providers/profile_provider.dart';

/// The 5-step offline-first onboarding flow.
/// On completion, writes all collected data to LocalStorageService and
/// navigates to the main app shell.
class OnboardingScreen extends StatefulWidget {
  final VoidCallback onComplete;

  static const List<String> avatars = [
    'assets/avatars/avatar_1.png',
    'assets/avatars/avatar_2.png',
    'assets/avatars/avatar_3.png',
    'assets/avatars/avatar_4.png',
  ];

  const OnboardingScreen({super.key, required this.onComplete});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen>
    with TickerProviderStateMixin {
  final PageController _pageController = PageController();
  int _currentPage = 0;
  static const int _totalPages = 5;

  // Step 1 – Language
  String _selectedLanguage = 'en';

  // Step 2 – Basic Profile
  final _nameController = TextEditingController();
  final _ageController = TextEditingController();
  final _heightController = TextEditingController();
  final _weightController = TextEditingController();
  String? _selectedAvatar;
  String? _nameError;
  String? _ageError;
  String? _heightError;
  String? _weightError;

  // Step 3 – Menstrual Profile
  DateTime? _lastPeriodDate;
  int _cycleLength = 28;
  int _periodDuration = 5;
  bool _isRegular = true;

  // Step 4 – Optional Info
  final _phoneController = TextEditingController();
  final _cityController = TextEditingController();
  final _stateController = TextEditingController();

  // Step 5 – Permissions
  bool _notificationsEnabled = false;
  bool _dataConsent = false;
  String? _consentError;
  String? _phoneError;

  late AnimationController _pageAnimController;
  late Animation<double> _pageFade;

  @override
  void initState() {
    super.initState();
    _selectedLanguage = LocalStorageService.preferredLanguage;
    _selectedAvatar = OnboardingScreen.avatars.first;

    _pageAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _pageFade = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _pageAnimController, curve: Curves.easeInOut),
    );
    _pageAnimController.forward();
  }

  @override
  void dispose() {
    _pageController.dispose();
    _nameController.dispose();
    _ageController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    _phoneController.dispose();
    _cityController.dispose();
    _stateController.dispose();
    _pageAnimController.dispose();
    super.dispose();
  }

  // ── Data ──────────────────────────────────────────────────────────────────

  static const List<Map<String, String>> _languages = [
    {'code': 'en', 'label': 'English'},
    {'code': 'hi', 'label': 'हिन्दी'},
    {'code': 'ta', 'label': 'தமிழ்'},
    {'code': 'te', 'label': 'తెలుగు'},
    {'code': 'mr', 'label': 'मराठी'},
  ];

  // ── Navigation ────────────────────────────────────────────────────────────

  bool _validateCurrentPage() {
    final l = AppLocalizations.of(context)!;
    setState(() {
      _nameError = null;
      _ageError = null;
      _heightError = null;
      _weightError = null;
      _consentError = null;
      _phoneError = null;
    });

    if (_currentPage == 1) {
      bool valid = true;
      if (_nameController.text.trim().isEmpty) {
        setState(() => _nameError = l.onboardingNameRequired);
        valid = false;
      }
      final age = int.tryParse(_ageController.text);
      if (_ageController.text.isNotEmpty &&
          (age == null || age < 10 || age > 120)) {
        setState(() => _ageError = l.onboardingAgeInvalid);
        valid = false;
      }
      final h = double.tryParse(_heightController.text);
      if (_heightController.text.isNotEmpty &&
          (h == null || h < 50 || h > 250)) {
        setState(() => _heightError = l.onboardingHeightInvalid);
        valid = false;
      }
      final w = double.tryParse(_weightController.text);
      if (_weightController.text.isNotEmpty &&
          (w == null || w < 20 || w > 300)) {
        setState(() => _weightError = l.onboardingWeightInvalid);
        valid = false;
      }
      return valid;
    }

    if (_currentPage == 3) {
      final digitsOnly = _phoneController.text.replaceAll(RegExp(r'[^0-9]'), '');
      if (_phoneController.text.trim().isNotEmpty && (digitsOnly.length < 7 || digitsOnly.length > 15)) {
        setState(() => _phoneError = l.onboardingPhoneInvalid);
        return false;
      }
    }

    if (_currentPage == 4) {
      if (!_dataConsent) {
        setState(() => _consentError = l.onboardingDataConsentRequired);
        return false;
      }
    }

    return true;
  }

  void _next() async {
    if (!_validateCurrentPage()) return;

    if (_currentPage == 0) {
      await LocalStorageService.setPreferredLanguage(_selectedLanguage);
      if (!mounted) return;
      context.read<LocaleProvider>().setLocale(Locale(_selectedLanguage));
    }

    if (!mounted) return;

    if (_currentPage < _totalPages - 1) {
      _pageAnimController.reset();
      await _pageController.animateToPage(
        _currentPage + 1,
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeInOutCubic,
      );
      if (!mounted) return;
      setState(() => _currentPage++);
      _pageAnimController.forward();
    } else {
      await _saveAndComplete();
    }
  }

  void _back() async {
    if (_currentPage > 0) {
      _pageAnimController.reset();
      await _pageController.animateToPage(
        _currentPage - 1,
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeInOutCubic,
      );
      if (!mounted) return;
      setState(() => _currentPage--);
      _pageAnimController.forward();
    }
  }

  Future<void> _saveAndComplete() async {
    final profile = <String, dynamic>{
      'name': _nameController.text.trim().isEmpty
          ? 'User'
          : _nameController.text.trim(),
      'avatar': _selectedAvatar ?? 'assets/avatars/avatar_1.png',
      'language': _selectedLanguage,
    };
    final age = int.tryParse(_ageController.text);
    if (age != null) profile['age'] = age;
    final h = double.tryParse(_heightController.text);
    if (h != null) profile['height_cm'] = h;
    final w = double.tryParse(_weightController.text);
    if (w != null) profile['weight_kg'] = w;
    if (_lastPeriodDate != null) {
      profile['last_period'] =
          _lastPeriodDate!.toIso8601String().split('T').first;
    }
    profile['cycle_length'] = _cycleLength;
    profile['period_duration'] = _periodDuration;
    profile['cycle_regular'] = _isRegular;
    final phone = _phoneController.text.trim();
    if (phone.isNotEmpty) profile['phone'] = phone;
    final city = _cityController.text.trim();
    if (city.isNotEmpty) profile['city'] = city;
    final state = _stateController.text.trim();
    if (state.isNotEmpty) profile['state'] = state;
    profile['notifications_enabled'] = _notificationsEnabled;

    // 1. Persist locally first — data is never lost even if backend is down.
    await context.read<ProfileProvider>().saveProfile(profile);

    // 2. Sync to backend is optional for now. The app uses local storage as
    // the source of truth. A background sync can be added later.
    // (Previously this called ProfileService.patchProfile, which was removed.)

    // 3. Mark onboarding done for this user account.
    await LocalStorageService.setOnboardingCompleted(true);

    widget.onComplete();
  }

  // ── UI ────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: RhythmaColors.background,
        body: SafeArea(
          child: Column(
            children: [
              _buildProgressBar(),
              Expanded(
                child: FadeTransition(
                  opacity: _pageFade,
                  child: PageView(
                    controller: _pageController,
                    physics: const NeverScrollableScrollPhysics(),
                    children: [
                      _buildStep1(l),
                      _buildStep2(l),
                      _buildStep3(l),
                      _buildStep4(l),
                      _buildStep5(l),
                    ],
                  ),
                ),
              ),
              _buildNavBar(l),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildProgressBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 0),
      child: Row(
        children: List.generate(_totalPages, (i) {
          final active = i <= _currentPage;
          return Expanded(
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              margin: const EdgeInsets.symmetric(horizontal: 3),
              height: 4,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(2),
                color: active
                    ? RhythmaColors.primary
                    : RhythmaColors.primary.withOpacity(0.2),
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildNavBar(AppLocalizations l) {
    final isLast = _currentPage == _totalPages - 1;
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
      child: Row(
        children: [
          if (_currentPage > 0)
            Expanded(
              child: OutlinedButton(
                onPressed: _back,
                style: OutlinedButton.styleFrom(
                  foregroundColor: RhythmaColors.primary,
                  side: BorderSide(color: RhythmaColors.primary),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
                child: Text(l.onboardingBack),
              ),
            ),
          if (_currentPage > 0) const SizedBox(width: 12),
          Expanded(
            flex: 2,
            child: ElevatedButton(
              onPressed: _next,
              style: ElevatedButton.styleFrom(
                backgroundColor: RhythmaColors.primary,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14)),
                elevation: 0,
              ),
              child: Text(
                isLast ? l.onboardingDone : l.onboardingNext,
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
    );
  }

  // ── Step 1 ────────────────────────────────────────────────────────────────

  Widget _buildStep1(AppLocalizations l) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildStepHeader(l.onboardingStep1Title, l.onboardingStep1Subtitle),
          const SizedBox(height: 32),
          ...List.generate(_languages.length, (i) {
            final lang = _languages[i];
            final selected = lang['code'] == _selectedLanguage;
            return GestureDetector(
              onTap: () {
                setState(() => _selectedLanguage = lang['code']!);
                context.read<LocaleProvider>().setLocale(Locale(lang['code']!));
              },
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                margin: const EdgeInsets.only(bottom: 12),
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  color: selected
                      ? RhythmaColors.primary.withOpacity(0.15)
                      : RhythmaColors.surface,
                  border: Border.all(
                    color:
                        selected ? RhythmaColors.primary : Colors.transparent,
                    width: 2,
                  ),
                ),
                child: Row(
                  children: [
                    Text(
                      lang['label']!,
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
            );
          }),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              color: RhythmaColors.primary.withOpacity(0.08),
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
        ],
      ),
    );
  }

  // ── Step 2 ────────────────────────────────────────────────────────────────

  Widget _buildStep2(AppLocalizations l) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildStepHeader(l.onboardingStep2Title, l.onboardingStep2Subtitle),
          const SizedBox(height: 28),
          Text(
            l.onboardingAvatarLabel,
            style: TextStyle(fontSize: 14, color: RhythmaColors.mutedFg),
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 70,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: OnboardingScreen.avatars.length,
              itemBuilder: (_, i) {
                final avatarPath = OnboardingScreen.avatars[i];
                final selected = _selectedAvatar == avatarPath;
                return GestureDetector(
                  onTap: () => setState(() => _selectedAvatar = avatarPath),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    margin: const EdgeInsets.only(right: 12),
                    width: 60,
                    height: 60,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: selected
                          ? RhythmaColors.primary.withOpacity(0.2)
                          : RhythmaColors.surface,
                      border: Border.all(
                        color: selected
                            ? RhythmaColors.primary
                            : Colors.transparent,
                        width: 2.5,
                      ),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(3.0),
                      child: CircleAvatar(
                        backgroundImage: AssetImage(avatarPath),
                        backgroundColor: Colors.transparent,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 24),
          _buildTextField(
            controller: _nameController,
            label: l.onboardingNameLabel,
            hint: l.onboardingNameHint,
            error: _nameError,
            textInputAction: TextInputAction.next,
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _ageController,
            label: l.onboardingAgeLabel,
            error: _ageError,
            keyboardType: TextInputType.number,
            textInputAction: TextInputAction.next,
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _buildTextField(
                  controller: _heightController,
                  label: l.onboardingHeightLabel,
                  error: _heightError,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  textInputAction: TextInputAction.next,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: _buildTextField(
                  controller: _weightController,
                  label: l.onboardingWeightLabel,
                  error: _weightError,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  textInputAction: TextInputAction.done,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ── Step 3 ────────────────────────────────────────────────────────────────

  Widget _buildStep3(AppLocalizations l) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildStepHeader(l.onboardingStep3Title, l.onboardingStep3Subtitle),
          const SizedBox(height: 28),
          Text(l.onboardingLastPeriodLabel,
              style: TextStyle(fontSize: 14, color: RhythmaColors.mutedFg)),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: () async {
              final picked = await showDatePicker(
                context: context,
                initialDate: _lastPeriodDate ??
                    DateTime.now().subtract(const Duration(days: 14)),
                firstDate: DateTime.now().subtract(const Duration(days: 365)),
                lastDate: DateTime.now(),
                builder: (context, child) {
                  final isDark =
                      Theme.of(context).brightness == Brightness.dark;
                  return Theme(
                    data: Theme.of(context).copyWith(
                      colorScheme: isDark
                          ? ColorScheme.dark(
                              primary: RhythmaColors.primary,
                              onPrimary: RhythmaColors.primaryFg,
                              surface: RhythmaColors.surface,
                              onSurface: RhythmaColors.foreground,
                            )
                          : ColorScheme.light(
                              primary: RhythmaColors.primary,
                              onPrimary: RhythmaColors.primaryFg,
                              surface: RhythmaColors.surface,
                              onSurface: RhythmaColors.foreground,
                            ),
                    ),
                    child: child!,
                  );
                },
              );
              if (picked != null) setState(() => _lastPeriodDate = picked);
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                color: RhythmaColors.surface,
                border:
                    Border.all(color: RhythmaColors.primary.withOpacity(0.3)),
              ),
              child: Row(
                children: [
                  Icon(Icons.calendar_today_rounded,
                      color: RhythmaColors.primary, size: 20),
                  const SizedBox(width: 12),
                  Text(
                    _lastPeriodDate == null
                        ? l.onboardingTapToSelectDate
                        : '${_lastPeriodDate!.day}/${_lastPeriodDate!.month}/${_lastPeriodDate!.year}',
                    style: TextStyle(
                      color: _lastPeriodDate == null
                          ? RhythmaColors.mutedFg
                          : RhythmaColors.foreground,
                      fontSize: 15,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          _buildSliderField(
            label: l.onboardingCycleLengthLabel,
            value: _cycleLength.toDouble(),
            min: 21,
            max: 45,
            divisions: 24,
            displayValue: '$_cycleLength ${l.onboardingDays}',
            onChanged: (v) => setState(() => _cycleLength = v.round()),
          ),
          const SizedBox(height: 20),
          _buildSliderField(
            label: l.onboardingPeriodDurationLabel,
            value: _periodDuration.toDouble(),
            min: 2,
            max: 10,
            divisions: 8,
            displayValue: '$_periodDuration ${l.onboardingDays}',
            onChanged: (v) => setState(() => _periodDuration = v.round()),
          ),
          const SizedBox(height: 24),
          Text(l.onboardingCycleRegularityLabel,
              style: TextStyle(fontSize: 14, color: RhythmaColors.mutedFg)),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                  child: _buildToggleChip(l.onboardingRegular, _isRegular,
                      () => setState(() => _isRegular = true))),
              const SizedBox(width: 12),
              Expanded(
                  child: _buildToggleChip(l.onboardingIrregular, !_isRegular,
                      () => setState(() => _isRegular = false))),
            ],
          ),
        ],
      ),
    );
  }

  // ── Step 4 ────────────────────────────────────────────────────────────────

  Widget _buildStep4(AppLocalizations l) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildStepHeader(l.onboardingStep4Title, l.onboardingStep4Subtitle),
          const SizedBox(height: 28),
          _buildTextField(
            controller: _phoneController,
            label: l.onboardingPhoneLabel,
            error: _phoneError,
            keyboardType: TextInputType.phone,
            textInputAction: TextInputAction.next,
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _cityController,
            label: l.onboardingCityLabel,
            textInputAction: TextInputAction.next,
          ),
          const SizedBox(height: 14),
          _buildTextField(
            controller: _stateController,
            label: l.onboardingStateLabel,
            textInputAction: TextInputAction.done,
          ),
        ],
      ),
    );
  }

  // ── Step 5 ────────────────────────────────────────────────────────────────

  Widget _buildStep5(AppLocalizations l) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 32, 24, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildStepHeader(l.onboardingStep5Title, l.onboardingStep5Subtitle),
          const SizedBox(height: 36),
          _buildSwitchTile(
            icon: '📅',
            title: l.onboardingEnableNotifications,
            subtitle: l.onboardingNotificationsDesc,
            value: _notificationsEnabled,
            onChanged: (v) => setState(() => _notificationsEnabled = v),
          ),
          const SizedBox(height: 32),
          GestureDetector(
            onTap: () {
              setState(() {
                _dataConsent = !_dataConsent;
                if (_dataConsent) _consentError = null;
              });
            },
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: 24,
                  height: 24,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(6),
                    color: _dataConsent
                        ? RhythmaColors.primary
                        : Colors.transparent,
                    border: Border.all(
                      color: _consentError != null
                          ? Colors.redAccent
                          : RhythmaColors.primary,
                      width: 2,
                    ),
                  ),
                  child: _dataConsent
                      ? const Icon(Icons.check, size: 16, color: Colors.white)
                      : null,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l.onboardingDataConsentLabel,
                        style: TextStyle(
                          color: RhythmaColors.foreground,
                          fontSize: 14,
                          height: 1.4,
                        ),
                      ),
                      if (_consentError != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          _consentError!,
                          style: const TextStyle(
                              color: Colors.redAccent, fontSize: 12),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── Shared helpers ────────────────────────────────────────────────────────

  Widget _buildStepHeader(String title, String subtitle) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Image.asset(
          'assets/images/logo.png',
          height: 48,
          fit: BoxFit.contain,
        ),
        const SizedBox(height: 12),
        Text(
          title,
          style: TextStyle(
            fontSize: 26,
            fontWeight: FontWeight.bold,
            color: RhythmaColors.foreground,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          subtitle,
          style: TextStyle(
            fontSize: 15,
            color: RhythmaColors.mutedFg,
            height: 1.5,
          ),
        ),
      ],
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    String? hint,
    String? error,
    TextInputType keyboardType = TextInputType.text,
    TextInputAction textInputAction = TextInputAction.next,
  }) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      textInputAction: textInputAction,
      style: TextStyle(color: RhythmaColors.foreground),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        errorText: error,
        labelStyle: TextStyle(color: RhythmaColors.mutedFg),
        hintStyle: TextStyle(color: RhythmaColors.mutedFg.withOpacity(0.6)),
        filled: true,
        fillColor: RhythmaColors.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: RhythmaColors.primary.withOpacity(0.2)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: RhythmaColors.primary, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Colors.redAccent, width: 1.5),
        ),
      ),
    );
  }

  Widget _buildSliderField({
    required String label,
    required double value,
    required double min,
    required double max,
    required int divisions,
    required String displayValue,
    required ValueChanged<double> onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(label,
                style: TextStyle(fontSize: 14, color: RhythmaColors.mutedFg)),
            const Spacer(),
            Text(
              displayValue,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: RhythmaColors.primary,
              ),
            ),
          ],
        ),
        Slider(
          value: value,
          min: min,
          max: max,
          divisions: divisions,
          activeColor: RhythmaColors.primary,
          inactiveColor: RhythmaColors.primary.withOpacity(0.2),
          onChanged: onChanged,
        ),
      ],
    );
  }

  Widget _buildToggleChip(String label, bool selected, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          color: selected
              ? RhythmaColors.primary.withOpacity(0.15)
              : RhythmaColors.surface,
          border: Border.all(
            color: selected ? RhythmaColors.primary : Colors.transparent,
            width: 2,
          ),
        ),
        child: Center(
          child: Text(
            label,
            style: TextStyle(
              fontWeight: selected ? FontWeight.bold : FontWeight.w500,
              color:
                  selected ? RhythmaColors.primary : RhythmaColors.foreground,
              fontSize: 15,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSwitchTile({
    required String icon,
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: RhythmaColors.surface,
        border: Border.all(
          color: value
              ? RhythmaColors.primary.withOpacity(0.4)
              : Colors.transparent,
        ),
      ),
      child: Row(
        children: [
          Text(icon, style: const TextStyle(fontSize: 28)),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: RhythmaColors.foreground,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 13,
                    color: RhythmaColors.mutedFg,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeThumbColor: RhythmaColors.primary,
          ),
        ],
      ),
    );
  }
}