import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../components/shared.dart';
import '../../components/charts.dart';
import '../../providers/theme_provider.dart';
import '../../services/api_client.dart';

/// All data on this screen comes from GET /dashboard — nothing here is
/// computed locally from Hive. That endpoint already returns real,
/// backend-computed CVI/MHS scores, cycle-length history, symptom
/// frequency, and the most recent stress level, so this screen is a thin
/// display layer over that one response.
class InsightsScreen extends StatefulWidget {
  const InsightsScreen({Key? key}) : super(key: key);

  @override
  State<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends State<InsightsScreen> {
  bool _loading = true;
  String _error = '';

  int? _mhs;
  String? _cvi;
  String? _sleepHours;
  int? _avgCycleLength;
  bool _hasEnoughData = false;
  List<int> _cycleLengthTrend = [];
  Map<String, double> _symptomFrequency = {};
  int? _recentStressLevel;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = '';
    });

    try {
      final response = await ApiClient.dio.get('/dashboard');
      final data = response.data as Map;
      final cycle = data['cycle'] as Map? ?? {};
      final insights = data['insights'] as Map? ?? {};
      final history = data['cycleHistory'] as List? ?? [];
      final symptomFreq = data['symptomFrequency'] as Map? ?? {};

      setState(() {
        _mhs = (insights['mhs'] as num?)?.round();
        _cvi = insights['cvi'] as String?;
        _sleepHours = insights['sleepHours'] as String?;
        _avgCycleLength = (cycle['total'] as num?)?.round();
        _hasEnoughData = data['hasEnoughDataForInsights'] == true;
        _cycleLengthTrend = history
            .map((e) => (e as Map)['cycle_length'])
            .whereType<num>()
            .map((n) => n.toInt())
            .toList();
        _symptomFrequency = symptomFreq.map((k, v) => MapEntry(k.toString(), (v as num).toDouble()));
        _recentStressLevel = (data['recentStressLevel'] as num?)?.toInt();
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  int _variability(List<int> lengths) {
    if (lengths.length < 2) return 0;
    final mean = lengths.reduce((a, b) => a + b) / lengths.length;
    final variance =
        lengths.map((v) => (v - mean) * (v - mean)).reduce((a, b) => a + b) / lengths.length;
    return variance <= 0 ? 0 : variance.round();
  }

  String _symptomLabel(String key, AppLocalizations l10n) {
    switch (key) {
      case 'cramps':
        return l10n.logSympCramps;
      case 'headache':
        return l10n.logSympHeadache;
      case 'bloating':
        return l10n.logSympBloating;
      case 'acne':
        return l10n.logSympAcne;
      default:
        return key;
    }
  }

  String _stressLabel(int? level, AppLocalizations l10n) {
    if (level == null) return '—';
    if (level <= 2) return l10n.logEnergyLow;
    if (level <= 3) return l10n.logEnergyMid;
    return l10n.logEnergyHigh;
  }

  List<Widget> _buildRecommendations(AppLocalizations l10n) {
    final recs = <Widget>[_Rec(l10n.insightsRec1, RhythmaColors.rose)];

    final sleepNum = double.tryParse((_sleepHours ?? '').replaceAll('h', ''));
    if (sleepNum != null && sleepNum < 7) {
      recs.add(_Rec(l10n.insightsRec2, RhythmaColors.primary));
    }
    if ((_recentStressLevel ?? 0) >= 4) {
      recs.add(_Rec(l10n.insightsRec3, RhythmaColors.teal));
    }
    if (recs.length == 1) {
      recs.add(_Rec(l10n.insightsRec2, RhythmaColors.primary));
      recs.add(_Rec(l10n.insightsRec3, RhythmaColors.teal));
    }
    return recs;
  }

  @override
  Widget build(BuildContext context) {
    context.watch<ThemeProvider>();
    final l10n = AppLocalizations.of(context)!;

    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    final variability = _variability(_cycleLengthTrend);
    final isStable = variability <= 3;

    return RefreshIndicator(
      onRefresh: _load,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(2, 8, 2, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n.insightsTitle,
                    style: TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w700,
                      color: RhythmaColors.foreground,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(l10n.insightsSubtitle,
                      style: TextStyle(fontSize: 13, color: RhythmaColors.mutedFg)),
                ],
              ),
            ),

            if (_error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: GlassCard(
                  child: Row(
                    children: [
                      Icon(Icons.error_outline, color: RhythmaColors.rose, size: 20),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          l10n.insightsLoadError(_error),
                          style: TextStyle(color: RhythmaColors.mutedFg, fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else if (!_hasEnoughData)
              Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: GlassCard(
                  child: Row(
                    children: [
                      Icon(Icons.hourglass_top_rounded, color: RhythmaColors.primary, size: 20),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          l10n.insightsNotEnoughData,
                          style: TextStyle(color: RhythmaColors.mutedFg, fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            // MHS hero card
            GlassCard(
              child: Stack(
                children: [
                  Positioned(
                    right: -30,
                    top: -30,
                    child: Container(
                      width: 160,
                      height: 160,
                      decoration: BoxDecoration(
                        gradient: RhythmaGradients.primary,
                        shape: BoxShape.circle,
                      ),
                    ).opacity(0.2),
                  ),
                  Row(
                    children: [
                      ScoreRing(value: _mhs ?? 0, size: 96),
                      const SizedBox(width: 18),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              l10n.insightsMhsLabel,
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                color: RhythmaColors.primary,
                                letterSpacing: 0.8,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Text(
                              _mhs != null ? '$_mhs / 100' : '— / 100',
                              style: TextStyle(
                                fontSize: 28,
                                fontWeight: FontWeight.w700,
                                color: RhythmaColors.foreground,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Row(
                              children: [
                                Icon(Icons.info_outline_rounded, size: 14, color: RhythmaColors.mutedFg),
                                const SizedBox(width: 5),
                                Expanded(
                                  child: Text(
                                    _cvi != null ? '${l10n.insightsRegular} · CVI: $_cvi' : l10n.insightsMhsDelta,
                                    style: TextStyle(fontSize: 12, color: RhythmaColors.mutedFg),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 14),

            // Mini stat grid
            Row(
              children: [
                Expanded(
                  child: _MiniCard(
                    label: l10n.insightsVar,
                    value: _cycleLengthTrend.length >= 2 ? '$variability ${l10n.homeDaysLabel}' : '—',
                    delta: isStable ? l10n.logEnergyLow : l10n.insightsModerate,
                    trendUp: false,
                    color: RhythmaColors.teal,
                    icon: Icons.graphic_eq_rounded,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _MiniCard(
                    label: l10n.insightsAvgCycle,
                    value: _avgCycleLength != null ? '$_avgCycleLength ${l10n.homeDaysLabel}' : '—',
                    delta: l10n.insightsRegular,
                    trendUp: true,
                    color: RhythmaColors.primary,
                    icon: Icons.favorite_rounded,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: _MiniCard(
                    label: l10n.homeLogSleep,
                    value: _sleepHours ?? '—',
                    delta: '',
                    trendUp: true,
                    color: RhythmaColors.primary,
                    icon: Icons.bedtime_rounded,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _MiniCard(
                    label: l10n.homeLogStress,
                    value: _stressLabel(_recentStressLevel, l10n),
                    delta: '',
                    trendUp: false,
                    color: RhythmaColors.coral,
                    icon: Icons.self_improvement_rounded,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 14),

            // Trend chart
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              l10n.insightsTrendLabel,
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                color: RhythmaColors.mutedFg,
                                letterSpacing: 0.8,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              isStable ? l10n.insightsStabilizing : l10n.insightsModerate,
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                color: RhythmaColors.foreground,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                        decoration: BoxDecoration(
                          color: (isStable ? RhythmaColors.teal : RhythmaColors.coral).withOpacity(0.14),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          isStable ? l10n.insightsHealthy : l10n.insightsModerate,
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: isStable ? RhythmaColors.teal : RhythmaColors.coral,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  if (_cycleLengthTrend.length < 2)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 24),
                      child: Center(
                        child: Text(
                          l10n.insightsNotEnoughTrendData,
                          textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 12, color: RhythmaColors.mutedFg),
                        ),
                      ),
                    )
                  else
                    TrendChart(
                      points: _cycleLengthTrend.map((e) => e.toDouble()).toList(),
                      color: RhythmaColors.primary,
                      height: 80,
                    ),
                ],
              ),
            ),

            const SizedBox(height: 14),

            // Symptom patterns
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n.insightsSymptomsLabel,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: RhythmaColors.foreground,
                    ),
                  ),
                  const SizedBox(height: 14),
                  if (_symptomFrequency.isEmpty)
                    Text(
                      l10n.insightsNoSymptomsYet,
                      style: TextStyle(fontSize: 12, color: RhythmaColors.mutedFg),
                    )
                  else ...[
                    _SymptomBar(_symptomLabel('cramps', l10n), _symptomFrequency['cramps'] ?? 0, RhythmaColors.rose),
                    const SizedBox(height: 12),
                    _SymptomBar(
                        _symptomLabel('headache', l10n), _symptomFrequency['headache'] ?? 0, RhythmaColors.coral),
                    const SizedBox(height: 12),
                    _SymptomBar(
                        _symptomLabel('bloating', l10n), _symptomFrequency['bloating'] ?? 0, RhythmaColors.primary),
                    const SizedBox(height: 12),
                    _SymptomBar(_symptomLabel('acne', l10n), _symptomFrequency['acne'] ?? 0, RhythmaColors.teal),
                  ],
                ],
              ),
            ),

            const SizedBox(height: 14),

            // Wellness recommendations
            SectionHeader(title: l10n.insightsWellnessLabel),
            ..._buildRecommendations(l10n).map((r) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: r,
                )),
          ],
        ),
      ),
    );
  }
}

class _MiniCard extends StatelessWidget {
  final String label;
  final String value;
  final String delta;
  final bool trendUp;
  final Color color;
  final IconData icon;

  const _MiniCard({
    required this.label,
    required this.value,
    required this.delta,
    required this.trendUp,
    required this.color,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 17),
              ),
              Icon(
                trendUp ? Icons.trending_up_rounded : Icons.trending_down_rounded,
                size: 16,
                color: color,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            label,
            style: TextStyle(fontSize: 11, color: RhythmaColors.mutedFg),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: RhythmaColors.foreground,
              height: 1,
            ),
          ),
          if (delta.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              delta,
              style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w600),
            ),
          ],
        ],
      ),
    );
  }
}

class _SymptomBar extends StatelessWidget {
  final String label;
  final double fraction;
  final Color color;

  const _SymptomBar(this.label, this.fraction, this.color);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label,
                style: TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600, color: RhythmaColors.foreground)),
            Text('${(fraction * 100).round()}%',
                style: TextStyle(fontSize: 12, color: RhythmaColors.mutedFg)),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: fraction,
            minHeight: 8,
            backgroundColor: RhythmaColors.surfaceMuted,
            valueColor: AlwaysStoppedAnimation(color),
          ),
        ),
      ],
    );
  }
}

class _Rec extends StatelessWidget {
  final String text;
  final Color color;

  const _Rec(this.text, this.color);

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
            child: Icon(Icons.favorite_rounded, color: Colors.white, size: 16),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 13,
                color: RhythmaColors.foreground,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

extension on Widget {
  Widget opacity(double v) => Opacity(opacity: v, child: this);
}