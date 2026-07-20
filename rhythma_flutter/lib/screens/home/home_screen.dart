import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../components/shared.dart';
import '../../components/charts.dart';
import '../../models/cycle_log.dart';
import '../../providers/theme_provider.dart';
import '../../providers/profile_provider.dart';
import '../../services/api_client.dart';
import '../../services/cycle_service.dart';
import '../../services/local_storage_service.dart';
import '../../utils/log_options.dart';
import '../cycle/components/log_entry_sheet.dart';
import '../insights/insights_screen.dart';
import '../settings/language_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _loading = true;
  Map<String, dynamic> _userData = {};
  Map<String, dynamic> _cycleData = {};
  Map<String, dynamic> _insights = {};
  String _error = '';

  @override
  void initState() {
    super.initState();
    _fetchDashboardData();
  }

  Future<void> _fetchDashboardData() async {
    setState(() => _loading = true);
    try {
      final dio = ApiClient.dio;
      final response = await dio.get('/dashboard');
      setState(() {
        _userData = response.data['user'] ?? {};
        _cycleData = response.data['cycle'] ?? {};
        _insights = response.data['insights'] ?? {};
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    context.watch<ThemeProvider>();
    final l10n = AppLocalizations.of(context)!;

    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error.isNotEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline,
                size: 48, color: RhythmaColors.rose),
            const SizedBox(height: 16),
            Text(
              l10n.homeFailedLoad,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Text(_error, style: TextStyle(color: RhythmaColors.mutedFg)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _fetchDashboardData,
              child: Text(l10n.homeRetry),
            ),
          ],
        ),
      );
    }

    final localProfile = context.watch<ProfileProvider>().profile;
    final localName = localProfile['name'] as String?;
    final apiName = _userData['name'] as String?;
    final userName = (localName != null && localName.isNotEmpty)
        ? localName
        : (apiName ?? 'User');

    final avatarPath =
        localProfile['avatar'] as String? ?? 'assets/avatars/avatar_1.png';
    final nextPeriodDays = _cycleData['nextPeriodDays'] ?? 14;
    final cycleDay = _cycleData['day'] ?? 14;
    final totalCycle = _cycleData['total'] ?? 28;
    final mhs = _insights['mhs'] ?? 82;
    final cvi = _insights['cvi'] ?? 'Low';
    final sleepHours = _insights['sleepHours'] ?? '7.2h';

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // ── Header ──────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(2, 8, 2, 20),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundImage: AssetImage(avatarPath),
                  backgroundColor: RhythmaColors.primary.withOpacity(0.15),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${l10n.homeGreeting}, $userName',
                        style: TextStyle(
                          fontSize: 26,
                          fontWeight: FontWeight.w700,
                          color: RhythmaColors.foreground,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        l10n.homePhaseDesc,
                        style: TextStyle(
                          fontSize: 13,
                          color: RhythmaColors.mutedFg,
                        ),
                      ),
                    ],
                  ),
                ),
                _HeaderIcon(
                  icon: Icons.language_rounded,
                  onTap: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const LanguageScreen()),
                    );
                  },
                ),
                const SizedBox(width: 8),
                _HeaderIcon(
                  icon: Icons.shield_outlined,
                  onTap: () =>
                      _showComingSoonDialog(context, l10n.homePrivacySecurity),
                ),
              ],
            ),
          ),

          // ── Cycle ring + prediction ──────────────────────────
          GlassCard(
            child: Stack(
              children: [
                Positioned(
                  right: -20,
                  top: -20,
                  child: Container(
                    width: 140,
                    height: 140,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: RhythmaGradients.primary,
                    ),
                  ).opacity(0.22),
                ),
                Column(
                  children: [
                    Row(
                      children: [
                        CycleRing(day: cycleDay, total: totalCycle, size: 88),
                        const SizedBox(width: 18),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                l10n.homeNextPeriod,
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  color: RhythmaColors.mutedFg,
                                  letterSpacing: 1,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.baseline,
                                textBaseline: TextBaseline.alphabetic,
                                children: [
                                  Text(
                                    '$nextPeriodDays',
                                    style: TextStyle(
                                      fontSize: 36,
                                      fontWeight: FontWeight.w700,
                                      color: RhythmaColors.foreground,
                                      height: 1,
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    l10n.homeDaysLabel,
                                    style: TextStyle(
                                      fontSize: 15,
                                      color: RhythmaColors.mutedFg,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              RichText(
                                text: TextSpan(
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: RhythmaColors.foreground,
                                  ),
                                  children: [
                                    TextSpan(text: l10n.homeFertileWindow),
                                    TextSpan(
                                      text: l10n.homeHighEnergy,
                                      style: const TextStyle(
                                        color: RhythmaColors.rose,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Container(
                      height: 1,
                      color: RhythmaColors.border,
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        _StatCell(
                            label: 'MHS',
                            value: '$mhs',
                            color: RhythmaColors.primary),
                        _StatDivider(),
                        _StatCell(
                            label: 'CVI',
                            value: '$cvi',
                            color: RhythmaColors.teal),
                        _StatDivider(),
                        _StatCell(
                            label: 'Sleep',
                            value: '$sleepHours',
                            color: RhythmaColors.coral),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 14),

          // ── AI Assistant CTA ────────────────────────────────
          GradientBox(
            padding: const EdgeInsets.all(18),
            child: Stack(
              children: [
                Positioned(
                  right: -8,
                  top: -8,
                  child: Icon(
                    Icons.auto_awesome_rounded,
                    size: 80,
                    color: Colors.white.withOpacity(0.15),
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.auto_awesome_rounded,
                            size: 14, color: Colors.white),
                        const SizedBox(width: 6),
                        Text(
                          l10n.homeAiTitle,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: Colors.white.withOpacity(0.9),
                            letterSpacing: 1,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      l10n.homeAiSubtitle,
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                        height: 1.3,
                      ),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        Expanded(
                          child: GestureDetector(
                            onTap: () {
                              Navigator.pushNamed(context, '/assistant');
                            },
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 14, vertical: 10),
                              decoration: BoxDecoration(
                                color: Colors.white.withOpacity(0.2),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Row(
                                children: [
                                  Icon(Icons.chat_bubble_outline_rounded,
                                      size: 15,
                                      color: Colors.white.withOpacity(0.9)),
                                  const SizedBox(width: 8),
                                  Text(
                                    l10n.homeAiPrompt,
                                    style: TextStyle(
                                      fontSize: 13,
                                      color: Colors.white.withOpacity(0.9),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.25),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: const Icon(Icons.mic_rounded,
                              size: 18, color: Colors.white),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 14),

          // ── Today's log ────────────────────────────────────
          SectionHeader(
            title: l10n.homeFeelingTitle,
            action: l10n.homeLogAll,
            onAction: () {
              final currentDate = DateTime.now();
              final dateKey = currentDate.toIso8601String().split('T')[0];
              final logs = LocalStorageService.getCycleLogs();
              final existingLog = logs.cast<Map<String, dynamic>?>().firstWhere(
                    (log) => log?['start_date'] == dateKey,
                    orElse: () => null,
                  );

              LogEntrySheet.show(
                context,
                currentDate,
                existingLog: existingLog,
              ).then((_) {
                setState(() {});
              });
            },
          ),
          Row(
            children: [
              _LogButton(
                icon: Icons.water_drop_outlined,
                label: l10n.homeLogFlow,
                color: RhythmaColors.rose,
                onTap: () => _showQuickLogSheet(
                  field: 'flow_intensity',
                  label: l10n.homeLogFlow,
                  icon: Icons.water_drop_outlined,
                  color: RhythmaColors.rose,
                  options: LogOptions.flow(l10n),
                ),
              ),
              const SizedBox(width: 10),
              _LogButton(
                icon: Icons.favorite_border_rounded,
                label: l10n.homeLogMood,
                color: RhythmaColors.coral,
                onTap: () => _showQuickLogSheet(
                  field: 'mood',
                  label: l10n.homeLogMood,
                  icon: Icons.favorite_border_rounded,
                  color: RhythmaColors.coral,
                  options: LogOptions.mood,
                ),
              ),
              const SizedBox(width: 10),
              _LogButton(
                icon: Icons.bedtime_outlined,
                label: l10n.homeLogSleep,
                color: RhythmaColors.primary,
                onTap: () => _showQuickLogSheet(
                  field: 'sleep_hours',
                  label: l10n.homeLogSleep,
                  icon: Icons.bedtime_outlined,
                  color: RhythmaColors.primary,
                  options: LogOptions.sleep(l10n),
                ),
              ),
              const SizedBox(width: 10),
              _LogButton(
                icon: Icons.air_rounded,
                label: l10n.homeLogStress,
                color: RhythmaColors.teal,
                onTap: () => _showQuickLogSheet(
                  field: 'stress_level',
                  label: l10n.homeLogStress,
                  icon: Icons.air_rounded,
                  color: RhythmaColors.teal,
                  options: LogOptions.stress(l10n),
                ),
              ),
            ],
          ),

          const SizedBox(height: 14),

          // ── Insight card ───────────────────────────────────
          GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (_) =>
                        const ShellBackground(child: InsightsScreen())),
              );
            },
            child: GlassCard(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          l10n.homeWeeklyInsightLabel,
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: RhythmaColors.teal,
                            letterSpacing: 1,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          l10n.homeWeeklyInsightTitle,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: RhythmaColors.foreground,
                            height: 1.35,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          l10n.homeWeeklyInsightDesc,
                          style: TextStyle(
                            fontSize: 13,
                            color: RhythmaColors.mutedFg,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Icon(Icons.chevron_right_rounded,
                      color: RhythmaColors.mutedFg),
                ],
              ),
            ),
          ),

          const SizedBox(height: 14),

          // ── Education cards ────────────────────────────────
          SectionHeader(title: l10n.homeLearnTitle),
          SizedBox(
            height: 128,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                _LearnCard(
                  title: l10n.homeLearnPcos,
                  color: RhythmaColors.rose,
                  label: l10n.homeArticle,
                  onTap: () =>
                      _showComingSoonDialog(context, l10n.homeLearnPcos),
                ),
                const SizedBox(width: 10),
                _LearnCard(
                  title: l10n.homeLearnHormones,
                  color: RhythmaColors.primary,
                  label: l10n.homeArticle,
                  onTap: () =>
                      _showComingSoonDialog(context, l10n.homeLearnHormones),
                ),
                const SizedBox(width: 10),
                _LearnCard(
                  title: l10n.homeLearnIron,
                  color: RhythmaColors.coral,
                  label: l10n.homeArticle,
                  onTap: () =>
                      _showComingSoonDialog(context, l10n.homeLearnIron),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ─── Helpers ────────────────────────────────────────────────────────────

  void _showComingSoonDialog(BuildContext context, String topic) {
    final l10n = AppLocalizations.of(context)!;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text(l10n.homeComingSoon,
            textAlign: TextAlign.center,
            style: TextStyle(color: RhythmaColors.primary)),
        content: Text(
          l10n.homeUnderDevelopment(topic),
          textAlign: TextAlign.center,
        ),
        actionsAlignment: MainAxisAlignment.center,
        actions: [
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: RhythmaColors.primary,
              foregroundColor: RhythmaColors.primaryFg,
            ),
            onPressed: () => Navigator.pop(ctx),
            child: Text(l10n.homeOk),
          ),
        ],
      ),
    );
  }

  dynamic _coerce(String field, String value) {
    if (field == 'sleep_hours') return double.tryParse(value) ?? value;
    if (field == 'stress_level') return int.tryParse(value) ?? value;
    return value;
  }

  CycleLog _buildQuickLog(String field, dynamic value) {
    final now = DateTime.now();
    switch (field) {
      case 'flow_intensity':
        return CycleLog(startDate: now, flowIntensity: value as String);
      case 'mood':
        return CycleLog(startDate: now, mood: value as String);
      case 'sleep_hours':
        return CycleLog(startDate: now, sleepHours: value as double);
      case 'stress_level':
        return CycleLog(startDate: now, stressLevel: value as int);
      default:
        return CycleLog(startDate: now);
    }
  }

  void _showQuickLogSheet({
    required String field,
    required String label,
    required IconData icon,
    required Color color,
    required List<LogOption> options,
  }) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
        child: Container(
          decoration: BoxDecoration(
            color: RhythmaColors.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          ),
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(icon, color: color, size: 17),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'Log $label',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: RhythmaColors.foreground,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: options.map((opt) {
                  return GestureDetector(
                    onTap: () async {
                      await LocalStorageService.saveQuickLogField(
                          DateTime.now(), field, _coerce(field, opt.value));
                      if (ctx.mounted) Navigator.pop(ctx);
                      if (!mounted) return;

                      final messenger = ScaffoldMessenger.of(context);

                      try {
                        await CycleService().submitLog(
                          _buildQuickLog(field, _coerce(field, opt.value)),
                        );
                        messenger.showSnackBar(
                          SnackBar(content: Text('$label logged: ${opt.label}')),
                        );
                        _fetchDashboardData();
                      } catch (_) {
                        messenger.showSnackBar(
                          const SnackBar(
                            content: Text(
                                "Saved on this device — couldn't reach the server yet."),
                          ),
                        );
                      }
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 9),
                      decoration: BoxDecoration(
                        color: RhythmaColors.surfaceMuted,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: RhythmaColors.border),
                      ),
                      child: Text(
                        opt.label,
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: RhythmaColors.foreground),
                      ),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Small helpers ──────────────────────────────────────────────────────────────

class _HeaderIcon extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;
  const _HeaderIcon({required this.icon, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: EdgeInsets.zero,
      borderRadius: 20,
      onTap: onTap,
      child: SizedBox(
        width: 38,
        height: 38,
        child: Icon(icon, size: 18, color: RhythmaColors.foreground),
      ),
    );
  }
}

class _StatCell extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatCell({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(label,
              style: TextStyle(
                  fontSize: 11,
                  color: RhythmaColors.mutedFg,
                  fontWeight: FontWeight.w500)),
          const SizedBox(height: 3),
          Text(value,
              style: TextStyle(
                  fontSize: 15, fontWeight: FontWeight.w700, color: color)),
        ],
      ),
    );
  }
}

class _StatDivider extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Container(
        width: 1,
        height: 28,
        color: RhythmaColors.border,
      );
}

class _LogButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback? onTap;

  const _LogButton(
      {required this.icon,
      required this.label,
      required this.color,
      this.onTap});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GlassCard(
        padding: const EdgeInsets.symmetric(vertical: 14),
        onTap: onTap,
        child: Column(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: color.withOpacity(0.15),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(height: 6),
            Text(label,
                style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: RhythmaColors.foreground)),
          ],
        ),
      ),
    );
  }
}

class _LearnCard extends StatelessWidget {
  final String title;
  final Color color;
  final String label;
  final VoidCallback? onTap;

  const _LearnCard(
      {required this.title,
      required this.color,
      required this.label,
      this.onTap});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 152,
        decoration: BoxDecoration(
          gradient: isDark
              ? null
              : LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    color,
                    Color.lerp(color, RhythmaColors.primary, 0.5)!
                  ],
                ),
          color: isDark ? color.withOpacity(0.15) : null,
          border: isDark ? Border.all(color: color.withOpacity(0.3)) : null,
          borderRadius: BorderRadius.circular(20),
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            Text(
              label,
              style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w700,
                  color: Colors.white.withOpacity(0.75),
                  letterSpacing: 1),
            ),
            const SizedBox(height: 4),
            Text(
              title,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: Colors.white,
                height: 1.25,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

extension on Widget {
  Widget opacity(double value) =>
      Opacity(opacity: value, child: this);
}