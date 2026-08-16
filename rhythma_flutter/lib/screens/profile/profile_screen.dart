import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../components/shared.dart';
import '../../config/theme.dart';
import '../../services/local_storage_service.dart';
import '../settings/settings_screen.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:url_launcher/url_launcher_string.dart';
import '../../providers/theme_provider.dart';
import '../../providers/profile_provider.dart';
import '../onboarding/onboarding_screen.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> with SingleTickerProviderStateMixin {
  String _userName = 'Aarya';
  int _userAge = 28;
  int _cycleLength = 28;
  final int _mhsAverage = 85;
  final int _cycleDay = 12;

  List<Map<String, String>> _emergencyContacts = [];

  late final AnimationController _controller;
  late final Animation<double> _headerFade;
  late final Animation<Offset> _headerSlide;
  late final Animation<double> _statsFade;
  late final Animation<Offset> _statsSlide;
  late final Animation<double> _menuFade;
  late final Animation<Offset> _menuSlide;

  @override
  void initState() {
    super.initState();
    _loadProfile();
    _loadEmergencyContacts();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );

    _headerFade = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.0, 0.5, curve: Curves.easeOut),
      ),
    );
    _headerSlide = Tween<Offset>(begin: const Offset(0, 0.08), end: Offset.zero).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.0, 0.5, curve: Curves.easeOutCubic),
      ),
    );

    _statsFade = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.2, 0.7, curve: Curves.easeOut),
      ),
    );
    _statsSlide = Tween<Offset>(begin: const Offset(0, 0.08), end: Offset.zero).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.2, 0.7, curve: Curves.easeOutCubic),
      ),
    );

    _menuFade = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.4, 0.9, curve: Curves.easeOut),
      ),
    );
    _menuSlide = Tween<Offset>(begin: const Offset(0, 0.08), end: Offset.zero).animate(
      CurvedAnimation(
        parent: _controller,
        curve: const Interval(0.4, 0.9, curve: Curves.easeOutCubic),
      ),
    );

    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _loadProfile() {
    final profile = LocalStorageService.getProfile();
    if (profile != null) {
      _userName = profile['name'] as String? ?? 'Aarya';
      _userAge = profile['age'] as int? ?? 28;
      _cycleLength = profile['cycle_length'] as int? ?? 28;
    }
  }

  void _loadEmergencyContacts() {
    _emergencyContacts = LocalStorageService.getEmergencyContacts();
  }

  String _getCyclePhase(int day) {
    if (day <= 5) return 'Menstrual Phase';
    if (day <= 13) return 'Follicular Phase';
    if (day == 14) return 'Ovulation Phase';
    return 'Luteal Phase';
  }

  void _showEditProfileSheet() {
    final profile = context.read<ProfileProvider>().profile;
    String selectedAvatar = profile['avatar'] as String? ?? 'assets/avatars/avatar_1.png';
    if (!selectedAvatar.startsWith('assets/') || !selectedAvatar.endsWith('.png')) {
      selectedAvatar = 'assets/avatars/avatar_1.png';
    }

    final nameController = TextEditingController(text: _userName);
    final ageController = TextEditingController(text: _userAge.toString());
    final cycleController = TextEditingController(text: _cycleLength.toString());

    String? nameError;
    String? ageError;
    String? cycleError;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(context).viewInsets.bottom,
          ),
          child: Container(
            decoration: BoxDecoration(
              color: RhythmaColors.surface,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            ),
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SectionHeader(title: AppLocalizations.of(context)!.profileEditProfile),
                const SizedBox(height: 16),
                Text(
                  AppLocalizations.of(context)!.onboardingAvatarLabel,
                  style: TextStyle(fontSize: 14, color: RhythmaColors.mutedFg),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  height: 64,
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    itemCount: OnboardingScreen.avatars.length,
                    itemBuilder: (_, i) {
                      final avatarPath = OnboardingScreen.avatars[i];
                      final isSelected = selectedAvatar == avatarPath;
                      return Semantics(
                        label: '${AppLocalizations.of(context)!.onboardingAvatarOption} ${i + 1}',
                        selected: isSelected,
                        button: true,
                        child: GestureDetector(
                          onTap: () => setSheetState(() => selectedAvatar = avatarPath),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            margin: const EdgeInsets.only(right: 12),
                            width: 54,
                            height: 54,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: isSelected
                                  ? RhythmaColors.primary.withOpacity(0.2)
                                  : RhythmaColors.surface,
                              border: Border.all(
                                color: isSelected ? RhythmaColors.primary : Colors.transparent,
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
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: nameController,
                  decoration: InputDecoration(
                    labelText: AppLocalizations.of(context)!.profileName,
                    errorText: nameError,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: ageController,
                  decoration: InputDecoration(
                    labelText: AppLocalizations.of(context)!.profileAge,
                    errorText: ageError,
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: cycleController,
                  decoration: InputDecoration(
                    labelText: AppLocalizations.of(context)!.profileAvgCycleDays,
                    errorText: cycleError,
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: () async {
                    setSheetState(() {
                      nameError = null;
                      ageError = null;
                      cycleError = null;
                    });

                    final name = nameController.text.trim();
                    final ageVal = int.tryParse(ageController.text);
                    final cycleVal = int.tryParse(cycleController.text);

                    bool isValid = true;

                    if (name.isEmpty) {
                      setSheetState(() => nameError = AppLocalizations.of(context)!.profileNameEmptyError);
                      isValid = false;
                    }

                    if (ageVal == null || ageVal < 10 || ageVal > 120) {
                      setSheetState(() => ageError = AppLocalizations.of(context)!.profileAgeInvalidError);
                      isValid = false;
                    }

                    if (cycleVal == null || cycleVal < 15 || cycleVal > 45) {
                      setSheetState(() => cycleError = AppLocalizations.of(context)!.profileCycleInvalidError);
                      isValid = false;
                    }

                    if (isValid) {
                      setState(() {
                        _userName = name;
                        _userAge = ageVal!;
                        _cycleLength = cycleVal!;
                      });
                      
                      await context.read<ProfileProvider>().mergeProfile({
                        'name': name,
                        'age': ageVal!,
                        'cycle_length': cycleVal!,
                        'avatar': selectedAvatar,
                      });

                      if (context.mounted) {
                        Navigator.pop(context);
                      }
                    }
                  },
                  child: Text(AppLocalizations.of(context)!.profileSaveChanges),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }

void _showAddEditContactDialog(
    int? editIndex,
    StateSetter setSheetState,
  ) {
    final contact =
        editIndex != null ? _emergencyContacts[editIndex] : null;

    final nameController =
        TextEditingController(text: contact?['name']);
    final phoneController =
        TextEditingController(text: contact?['phone']);

    String? nameError;
    String? phoneError;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => Semantics(
          label: editIndex == null
              ? AppLocalizations.of(context)!.profileAddContact
              : AppLocalizations.of(context)!.profileEditContact,
          child: AlertDialog(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
            ),
            title: Text(
              editIndex == null
                  ? AppLocalizations.of(context)!.profileAddContact
                  : AppLocalizations.of(context)!.profileEditContact,
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  textInputAction: TextInputAction.next,
                  decoration: InputDecoration(
                    labelText:
                        AppLocalizations.of(context)!.profileName,
                    errorText: nameError,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: phoneController,
                  keyboardType: TextInputType.phone,
                  textInputAction: TextInputAction.done,
                  decoration: InputDecoration(
                    labelText:
                        AppLocalizations.of(context)!.profilePhone,
                    errorText: phoneError,
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text(AppLocalizations.of(context)!.cancel),
              ),
              ElevatedButton(
                onPressed: () async {
                  setDialogState(() {
                    nameError = null;
                    phoneError = null;
                  });

                  final name = nameController.text.trim();
                  final phone = phoneController.text.trim();

                  bool isValid = true;

                  if (name.isEmpty) {
                    setDialogState(() {
                      nameError = AppLocalizations.of(context)!
                          .contactNameRequiredError;
                    });
                    isValid = false;
                  }

                  if (phone.isEmpty ||
                      phone.length < 8 ||
                      !RegExp(r'^\+?[0-9\s\-]+$').hasMatch(phone)) {
                    setDialogState(() {
                      phoneError = AppLocalizations.of(context)!
                          .profilePhoneInvalidError;
                    });
                    isValid = false;
                  }

                  if (!isValid) return;

                  setSheetState(() {
                    if (editIndex == null) {
                      _emergencyContacts.add({
                        'name': name,
                        'phone': phone,
                      });
                    } else {
                      _emergencyContacts[editIndex] = {
                        'name': name,
                        'phone': phone,
                      };
                    }
                  });

                  await LocalStorageService.saveEmergencyContacts(
                    _emergencyContacts,
                  );

                  if (context.mounted) {
                    Navigator.pop(context);
                  }
                },
                child: Text(
                  AppLocalizations.of(context)!.profileSave,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
  
  void _showEmergencyContactsSheet() {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => StatefulBuilder(
      builder: (context, setSheetState) {
        final contacts = _emergencyContacts;
        
        return Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(context).viewInsets.bottom,
          ),
          child: Container(
            decoration: BoxDecoration(
              color: RhythmaColors.surface,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            ),
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SectionHeader(
                  title: AppLocalizations.of(context)!.profileEmergencyContactsTitle,
                  action: AppLocalizations.of(context)!.profileAddNew,
                  onAction: () {
                    _showAddEditContactDialog(null, setSheetState);
                  },
                ),
                const SizedBox(height: 12),
                if (contacts.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 32),
                    child: Text(
                      AppLocalizations.of(context)!.profileNoContacts,
                      textAlign: TextAlign.center,
                      style: TextStyle(color: RhythmaColors.mutedFg),
                    ),
                  )
                else
                  Flexible(
                    child: ListView.separated(
                      shrinkWrap: true,
                      itemCount: contacts.length,
                      separatorBuilder: (context, index) => Divider(
                        height: 1,
                        color: RhythmaColors.border,
                      ),
                      itemBuilder: (context, index) {
                        final contact = contacts[index];
                        return ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const TintedIcon(
                            icon: Icons.contact_phone_rounded,
                            color: RhythmaColors.rose,
                            size: 36,
                          ),
                          title: Text(
                            contact['name'] ?? '',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text(
                            contact['phone'] ?? '',
                            style: TextStyle(color: RhythmaColors.mutedFg),
                          ),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                icon: const Icon(Icons.phone_rounded, size: 20),
                                tooltip: 'Call',
                                onPressed: () {
                                  final phone = contact['phone']?.replaceAll(RegExp(r'[^\d+]'), '');
                                  if (phone != null && phone.isNotEmpty) {
                                    launchUrlString('tel:$phone');
                                  }
                                },
                              ),
                              IconButton(
                                icon: const Icon(Icons.message_rounded, size: 20),
                                tooltip: 'SMS',
                                onPressed: () {
                                  final phone = contact['phone']?.replaceAll(RegExp(r'[^\d+]'), '');
                                  if (phone != null && phone.isNotEmpty) {
                                    launchUrlString('sms:$phone');
                                  }
                                },
                              ),
                              IconButton(
                                icon: const Icon(Icons.edit_rounded, size: 20),
                                tooltip: AppLocalizations.of(context)!.edit,
                                onPressed: () {
                                  _showAddEditContactDialog(index, setSheetState);
                                },
                              ),
                              IconButton(
                                icon: const Icon(Icons.delete_outline_rounded,
                                    color: RhythmaColors.coral, size: 20),
                                tooltip: AppLocalizations.of(context)!.delete,
                                onPressed: () async {
                                  setSheetState(() {
                                    _emergencyContacts.removeAt(index);
                                  });
                                  await LocalStorageService.saveEmergencyContacts(_emergencyContacts);
                                },
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        );
      },
    ),
  );
}

  Widget _buildHeader() {
    final profile = context.read<ProfileProvider>().profile;
    String avatarPath = profile['avatar'] as String? ?? 'assets/avatars/avatar_1.png';
    if (!avatarPath.startsWith('assets/') || !avatarPath.endsWith('.png')) {
      avatarPath = 'assets/avatars/avatar_1.png';
    }

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RhythmaGradients.primary,
          ),
          child: Container(
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: RhythmaColors.background,
            ),
            child: CircleAvatar(
              radius: 48,
              backgroundImage: AssetImage(avatarPath),
              backgroundColor: Colors.transparent,
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text(
          _userName,
          style: Theme.of(context).textTheme.displayLarge?.copyWith(fontSize: 24),
        ),
        const SizedBox(height: 4),
        Text(
          '$_userAge ${AppLocalizations.of(context)!.profileYearsOld}',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: RhythmaColors.mutedFg,
              ),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: RhythmaColors.teal.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: RhythmaColors.teal.withValues(alpha: 0.25),
              width: 0.8,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.water_drop, color: RhythmaColors.teal, size: 16),
              const SizedBox(width: 4),
              Text(
                '${AppLocalizations.of(context)!.profileCycleDay} $_cycleDay • ${_getCyclePhase(_cycleDay)}',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: RhythmaColors.teal,
                    ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildStatCard({
    required IconData icon,
    required Color color,
    required String value,
    required String label,
  }) {
    return GlassCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              TintedIcon(icon: icon, color: color, size: 28),
              Icon(
                Icons.trending_flat_rounded,
                color: color.withValues(alpha: 0.6),
                size: 16,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: RhythmaColors.foreground,
              height: 1.1,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: RhythmaColors.mutedFg,
              height: 1.1,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildStatsCards() {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _buildStatCard(
                icon: Icons.calendar_month_rounded,
                color: RhythmaColors.rose,
                value: '$_cycleLength ${AppLocalizations.of(context)!.homeDaysLabel}',
                label: AppLocalizations.of(context)!.profileAvgCycleLength,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildStatCard(
                icon: Icons.psychology_rounded,
                color: RhythmaColors.teal,
                value: '$_mhsAverage',
                label: AppLocalizations.of(context)!.profileAvgMentalHealth,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _buildStatCard(
                icon: Icons.insights_rounded,
                color: RhythmaColors.coral,
                value: '±1.2 ${AppLocalizations.of(context)!.homeDaysLabel}',
                label: AppLocalizations.of(context)!.profileCycleVariability,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildStatCard(
                icon: Icons.history_toggle_off_rounded,
                color: RhythmaColors.primary,
                value: '27 ${AppLocalizations.of(context)!.homeDaysLabel}',
                label: AppLocalizations.of(context)!.profileLastCycleLength,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildActionMenu() {
  return GlassCard(
    padding: EdgeInsets.zero,
    child: Column(
      children: [
        _buildActionTile(
          icon: Icons.edit_rounded,
          color: RhythmaColors.primary,
          title: AppLocalizations.of(context)!.profileEditInfo,
          onTap: _showEditProfileSheet,
        ),
        Divider(height: 1, color: RhythmaColors.border),
        _buildActionTile(
          icon: Icons.emergency_rounded,
          color: RhythmaColors.rose,
          title: AppLocalizations.of(context)!.profileEmergencyContact,
          onTap: _showEmergencyContactsSheet,
        ),
        Divider(height: 1, color: RhythmaColors.border),
        _buildActionTile(
          icon: Icons.settings_rounded,
          color: RhythmaColors.foreground,
          title: AppLocalizations.of(context)!.profileAppSettings,
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (context) => const SettingsScreen(),
              ),
            ).then((_) {
              setState(() {
                _loadProfile();
              });
            });
          },
        ),
      ],
    ),
  );
}

  Widget _buildActionTile({
    required IconData icon,
    required Color color,
    required String title,
    required VoidCallback onTap,
  }) {
    return Semantics(
      button: true,
      label: title,
      child: ListTile(
        leading: TintedIcon(icon: icon, color: color, size: 36),
        title: Text(title, style: Theme.of(context).textTheme.bodyLarge),
        trailing: ExcludeSemantics(
          child: Icon(Icons.chevron_right_rounded, color: RhythmaColors.mutedFg),
        ),
        onTap: onTap,
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    context.watch<ThemeProvider>();
    final profile = context.watch<ProfileProvider>().profile;
    if (profile.isNotEmpty) {
      _userName = profile['name'] as String? ?? 'Aarya';
      _userAge = profile['age'] as int? ?? 28;
      _cycleLength = profile['cycle_length'] as int? ?? 28;
    }
    return Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(20).copyWith(bottom: 100, top: 24),
        children: [
          FadeTransition(
            opacity: _headerFade,
            child: SlideTransition(
              position: _headerSlide,
              child: Column(
                children: [
                  Semantics(
                    header: true,
                    child: Text(
                      AppLocalizations.of(context)!.profileTitle,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontSize: 22,
                            fontWeight: FontWeight.w700,
                          ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: 32),
                  _buildHeader(),
                ],
              ),
            ),
          ),
          const SizedBox(height: 32),
          FadeTransition(
            opacity: _statsFade,
            child: SlideTransition(
              position: _statsSlide,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Semantics(
                    header: true,
                    child: SectionHeader(title: AppLocalizations.of(context)!.profileQuickStats),
                  ),
                  _buildStatsCards(),
                ],
              ),
            ),
          ),
          const SizedBox(height: 32),
          FadeTransition(
            opacity: _menuFade,
            child: SlideTransition(
              position: _menuSlide,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Semantics(
                    header: true,
                    child: SectionHeader(title: AppLocalizations.of(context)!.profileAccountSettings),
                  ),
                  _buildActionMenu(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
  }
