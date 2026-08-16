import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../providers/locale_provider.dart';
import '../../services/local_storage_service.dart';
import '../../services/profile_service.dart';
import '../../providers/profile_provider.dart';
import '../../components/approximate_field.dart';

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

  // Step 2 – "Not sure" toggle state
  bool _ageIsEstimated = false;
  String? _ageSelectedRange;
  bool _heightIsEstimated = false;
  String? _heightSelectedRange;
  bool _weightIsEstimated = false;
  String? _weightSelectedRange;

  // Step 3 – Menstrual Profile
  DateTime? _lastPeriodDate;
  bool _isLastPeriodApproximate = false;
  bool _showExactDatePicker = true;
  String? _lastPeriodError;
  int _selectedApproximateIndex = -1;
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

  // E.164 format: leading '+' followed by 1-15 digits.
  static final _e164 = RegExp(r'^\+[1-9]\d{1,14}$');

  List<ApproxRange> _buildAgeRanges(AppLocalizations l) => [
        const ApproxRange(key: 'under_18', label: 'Under 18', midpoint: 16),
        const ApproxRange(key: '18_25', label: '18-25', midpoint: 21.5),
        const ApproxRange(key: '26_35', label: '26-35', midpoint: 30.5),
        const ApproxRange(key: '36_45', label: '36-45', midpoint: 40.5),
        const ApproxRange(key: '46_plus', label: '46+', midpoint: 55),
      ];

  List<ApproxRange> _buildHeightRanges(AppLocalizations l) => [
        const ApproxRange(key: 'under_150', label: 'Under 150 cm', midpoint: 145),
        const ApproxRange(key: '150_160', label: '150-160 cm', midpoint: 155),
        const ApproxRange(key: '160_170', label: '160-170 cm', midpoint: 165),
        const ApproxRange(key: '170_180', label: '170-180 cm', midpoint: 175),
        const ApproxRange(key: '180_plus', label: '180+ cm', midpoint: 185),
      ];

  List<ApproxRange> _buildWeightRanges(AppLocalizations l) => [
        const ApproxRange(key: 'under_50', label: 'Under 50 kg', midpoint: 45),
        const ApproxRange(key: '50_60', label: '50-60 kg', midpoint: 55),
        const ApproxRange(key: '60_70', label: '60-70 kg', midpoint: 65),
        const ApproxRange(key: '70_80', label: '70-80 kg', midpoint: 75),
        const ApproxRange(key: '80_plus', label: '80+ kg', midpoint: 90),
      ];

  double? _getMidpoint(List<ApproxRange> ranges, String? selectedKey) {
    if (selectedKey == null) return null;
    for (final r in ranges) {
      if (r.key == selectedKey) return r.midpoint;
    }
    return null;
  }

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
      _lastPeriodError = null;
    });

    if (_currentPage == 1) {
      bool valid = true;
      if (_nameController.text.trim().isEmpty) {
        setState(() => _nameError = l.onboardingNameRequired);
        valid = false;
      }

      // Age – required
      if (_ageIsEstimated) {
        if (_ageSelectedRange == null) {
          setState(() => _ageError = l.onboardingAgeRequired);
          valid = false;
        }
      } else {
        if (_ageController.text.trim().isEmpty) {
          setState(() => _ageError = l.onboardingAgeRequired);
          valid = false;
        } else {
          final age = int.tryParse(_ageController.text);
          if (age == null || age < 1 || age > 120) {
            setState(() => _ageError = l.onboardingAgeInvalid);
            valid = false;
          }
        }
      }

      // Height – required
      if (_heightIsEstimated) {
        if (_heightSelectedRange == null) {
          setState(() => _heightError = l.onboardingHeightRequired);
          valid = false;
        }
      } else {
        if (_heightController.text.trim().isEmpty) {
          setState(() => _heightError = l.onboardingHeightRequired);
          valid = false;
        } else {
          final h = double.tryParse(_heightController.text);
          if (h == null || h < 50 || h > 250) {
            setState(() => _heightError = l.onboardingHeightInvalid);
            valid = false;
          }
        }
      }

      // Weight – required
      if (_weightIsEstimated) {
        if (_weightSelectedRange == null) {
          setState(() => _weightError = l.onboardingWeightRequired);
          valid = false;
        }
      } else {
        if (_weightController.text.trim().isEmpty) {
          setState(() => _weightError = l.onboardingWeightRequired);
          valid = false;
        } else {
          final w = double.tryParse(_weightController.text);
          if (w == null || w < 20 || w > 300) {
            setState(() => _weightError = l.onboardingWeightInvalid);
            valid = false;
          }
        }
      }

      return valid;
    }

    if (_currentPage == 2) {
      if (_lastPeriodDate == null) {
        setState(() => _lastPeriodError = l.onboardingLastPeriodRequired);
        return false;
      }
      return true;
    }

    if (_currentPage == 3) {
      final phone = _phoneController.text.trim();
      if (phone.isNotEmpty && !_e164.hasMatch(phone)) {
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
    final l = AppLocalizations.of(context)!;
    final profile = <String, dynamic>{
      'name': _nameController.text.trim().isEmpty
          ? 'User'
          : _nameController.text.trim(),
      'avatar': _selectedAvatar ?? 'assets/avatars/avatar_1.png',
      'language': _selectedLanguage,
    };
    final age = int.tryParse(_ageController.text);
    if (age != null) profile['age'] = age;
    profile['age_is_estimated'] = _ageIsEstimated;
    if (_ageIsEstimated) {
      final midpoint = _getMidpoint(_buildAgeRanges(l), _ageSelectedRange);
      if (midpoint != null) profile['age'] = midpoint;
    }
    final h = double.tryParse(_heightController.text);
    if (h != null) profile['height_cm'] = h;
    profile['height_is_estimated'] = _heightIsEstimated;
    if (_heightIsEstimated) {
      final midpoint = _getMidpoint(_buildHeightRanges(l), _heightSelectedRange);
      if (midpoint != null) profile['height_cm'] = midpoint;
    }
    final w = double.tryParse(_weightController.text);
    if (w != null) profile['weight_kg'] = w;
    profile['weight_is_estimated'] = _weightIsEstimated;
    if (_weightIsEstimated) {
      final midpoint = _getMidpoint(_buildWeightRanges(l), _weightSelectedRange);
      if (midpoint != null) profile['weight_kg'] = midpoint;
    }
    if (_lastPeriodDate != null) {
      profile['last_period'] =
          _lastPeriodDate!.toIso8601String().split('T').first;
      profile['last_period_is_approximate'] = _isLastPeriodApproximate;
    }
    profile['onboarding_completed_at'] =
        DateTime.now().toIso8601String().split('T').first;
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
    await context.read<ProfileProvider>().mergeProfileWithSync(profile);

    // 2. Sync to backend — best-effort, never blocks the user.
    ProfileService.patchProfile(profile);

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
                    : RhythmaColors.primary.withValues(alpha: 0.2),
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
                      ? RhythmaColors.primary.withValues(alpha: 0.15)
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
                          ? RhythmaColors.primary.withValues(alpha: 0.2)
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
          ApproximateField(
            label: l.onboardingAgeLabel,
            hint: l.onboardingAgeHint,
            unit: l.onboardingAgeUnit,
            ranges: _buildAgeRanges(l),
            controller: _ageController,
            isEstimated: _ageIsEstimated,
            onEstimatedChanged: (v) => setState(() {
              _ageIsEstimated = v;
              _ageError = null;
            }),
            selectedRange: _ageSelectedRange,
            onRangeChanged: (v) => setState(() {
              _ageSelectedRange = v;
              _ageError = null;
            }),
            error: _ageError,
            minValue: 1,
            maxValue: 120,
            toggleLabel: l.onboardingNotSure,
            approximateLabel: l.onboardingApproximate,
          ),
          const SizedBox(height: 14),
          // Height & Weight: side-by-side in exact mode; vertical when
          // either enters approximate mode to avoid overflow on small screens.
          if (_heightIsEstimated || _weightIsEstimated) ...[
            ApproximateField(
              label: l.onboardingHeightLabel,
              hint: l.onboardingHeightHint,
              unit: l.onboardingHeightUnit,
              ranges: _buildHeightRanges(l),
              controller: _heightController,
              isEstimated: _heightIsEstimated,
              onEstimatedChanged: (v) => setState(() {
                _heightIsEstimated = v;
                _heightError = null;
              }),
              selectedRange: _heightSelectedRange,
              onRangeChanged: (v) => setState(() {
                _heightSelectedRange = v;
                _heightError = null;
              }),
              error: _heightError,
              isDecimal: true,
              minValue: 50,
              maxValue: 250,
              toggleLabel: l.onboardingNotSure,
              approximateLabel: l.onboardingApproximate,
            ),
            const SizedBox(height: 14),
            ApproximateField(
              label: l.onboardingWeightLabel,
              hint: l.onboardingWeightHint,
              unit: l.onboardingWeightUnit,
              ranges: _buildWeightRanges(l),
              controller: _weightController,
              isEstimated: _weightIsEstimated,
              onEstimatedChanged: (v) => setState(() {
                _weightIsEstimated = v;
                _weightError = null;
              }),
              selectedRange: _weightSelectedRange,
              onRangeChanged: (v) => setState(() {
                _weightSelectedRange = v;
                _weightError = null;
              }),
              error: _weightError,
              isDecimal: true,
              minValue: 20,
              maxValue: 300,
              toggleLabel: l.onboardingNotSure,
              approximateLabel: l.onboardingApproximate,
            ),
          ] else ...[
            Row(
              children: [
                Expanded(
                  child: ApproximateField(
                    label: l.onboardingHeightLabel,
                    hint: l.onboardingHeightHint,
                    unit: l.onboardingHeightUnit,
                    ranges: _buildHeightRanges(l),
                    controller: _heightController,
                    isEstimated: _heightIsEstimated,
                    onEstimatedChanged: (v) => setState(() {
                      _heightIsEstimated = v;
                      _heightError = null;
                    }),
                    selectedRange: _heightSelectedRange,
                    onRangeChanged: (v) => setState(() {
                      _heightSelectedRange = v;
                      _heightError = null;
                    }),
                    error: _heightError,
                    isDecimal: true,
                    minValue: 50,
                    maxValue: 250,
                    toggleLabel: l.onboardingNotSure,
                    approximateLabel: l.onboardingApproximate,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: ApproximateField(
                    label: l.onboardingWeightLabel,
                    hint: l.onboardingWeightHint,
                    unit: l.onboardingWeightUnit,
                    ranges: _buildWeightRanges(l),
                    controller: _weightController,
                    isEstimated: _weightIsEstimated,
                    onEstimatedChanged: (v) => setState(() {
                      _weightIsEstimated = v;
                      _weightError = null;
                    }),
                    selectedRange: _weightSelectedRange,
                    onRangeChanged: (v) => setState(() {
                      _weightSelectedRange = v;
                      _weightError = null;
                    }),
                    error: _weightError,
                    isDecimal: true,
                    minValue: 20,
                    maxValue: 300,
                    toggleLabel: l.onboardingNotSure,
                    approximateLabel: l.onboardingApproximate,
                  ),
                ),
              ],
            ),
          ],
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
          Text(
  l.onboardingLastPeriodLabel,
  style: TextStyle(
    fontSize: 14,
    color: RhythmaColors.mutedFg,
  ),
),

const SizedBox(height: 4),

Text(
  'Choose the first day of your last period.',
  style: TextStyle(
    fontSize: 12,
    color: RhythmaColors.mutedFg,
  ),
),

const SizedBox(height: 8),

Semantics(
  label: 'Last period date',
  hint: 'Double tap to open calendar and select a date',
  button: true,
  child: GestureDetector(
    onTap: () async {
      final picked = await showDatePicker(
        context: context,
        initialDate: _lastPeriodDate ??
            DateTime.now().subtract(const Duration(days: 14)),
        firstDate: DateTime.now().subtract(const Duration(days: 365)),
        lastDate: DateTime.now(),
      );

      if (picked != null) {
        setState(() => _lastPeriodDate = picked);
      }
    },
    child: Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 16,
        vertical: 14,
      ),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        color: RhythmaColors.surface,
      ),
      child: Row(
        children: [
          Icon(
            Icons.calendar_today_rounded,
            color: RhythmaColors.primary,
            size: 20,
          ),
          const SizedBox(width: 12),
          Text(
            _lastPeriodDate == null
                ? l.onboardingTapToSelectDate
                : '${_lastPeriodDate!.day}/${_lastPeriodDate!.month}/${_lastPeriodDate!.year}',
          ),
        ],
      ),
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
            hint: l.onboardingPhoneHint,
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
        _buildStepHeader(
          l.onboardingStep5Title,
          l.onboardingStep5Subtitle,
        ),
        const SizedBox(height: 36),

        _buildSwitchTile(
          icon: '📅',
          title: l.onboardingEnableNotifications,
          subtitle: l.onboardingNotificationsDesc,
          value: _notificationsEnabled,
          onChanged: (v) =>
              setState(() => _notificationsEnabled = v),
        ),

        const SizedBox(height: 20),

        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: RhythmaColors.primary.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            'We use your cycle information to provide predictions and reminders. Your information stays private, and you can change these settings later.',
            style: TextStyle(
              fontSize: 13,
              color: RhythmaColors.mutedFg,
              height: 1.5,
            ),
          ),
        ),

        const SizedBox(height: 32),

        Semantics(
          label: 'Data consent',
          hint: 'Double tap to agree to data usage',
          checked: _dataConsent,
          child: GestureDetector(
            onTap: () {
              setState(() {
                _dataConsent = !_dataConsent;
                if (_dataConsent) {
                  _consentError = null;
                }
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
                      ? const Icon(
                          Icons.check,
                          size: 16,
                          color: Colors.white,
                        )
                      : null,
                ),

                const SizedBox(width: 12),

                Expanded(
                  child: Column(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
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
                            color: Colors.redAccent,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
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
        hintStyle: TextStyle(color: RhythmaColors.mutedFg.withValues(alpha: 0.6)),
        filled: true,
        fillColor: RhythmaColors.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: RhythmaColors.primary.withValues(alpha: 0.2)),
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
          inactiveColor: RhythmaColors.primary.withValues(alpha: 0.2),
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
          ? RhythmaColors.primary.withValues(alpha: 0.15)
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

  Widget _buildApproximateChip(String label, int daysAgo, int index) {
    final selected =
        _isLastPeriodApproximate && _selectedApproximateIndex == index;
    return GestureDetector(
      onTap: () {
        setState(() {
          _lastPeriodDate = DateTime.now().subtract(Duration(days: daysAgo));
          _isLastPeriodApproximate = true;
          _selectedApproximateIndex = index;
          _showExactDatePicker = false;
          _lastPeriodError = null;
        });
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          color: selected
              ? RhythmaColors.primary.withValues(alpha: 0.15)
              : RhythmaColors.surface,
          border: Border.all(
            color: selected ? RhythmaColors.primary : RhythmaColors.border,
            width: 1.5,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
            color: selected ? RhythmaColors.primary : RhythmaColors.foreground,
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
          ? RhythmaColors.primary.withValues(alpha: 0.4)
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
         
          Semantics(
            label: 'Cycle reminders',
            hint: 'Turn reminders on or off',
            child: Switch(
             value: value,
             onChanged: onChanged,
             activeThumbColor: RhythmaColors.primary,
            ),
          ),
        ],
      ),
    );
   }
  }

