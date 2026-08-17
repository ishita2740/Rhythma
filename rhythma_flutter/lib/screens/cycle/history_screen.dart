import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../config/theme.dart';
import '../../services/cycle_service.dart';
import '../../services/local_storage_service.dart';
import '../../components/shared.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final _scrollController = ScrollController();
  final _cycleService = CycleService();
  
  List<Map<String, dynamic>> _logs = [];
  bool _isLoading = true;
  bool _isLoadingMore = false;
  bool _hasMore = true;
  int _offset = 0;
  final int _limit = 15;

  @override
  void initState() {
    super.initState();
    _fetchLogs();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
            _scrollController.position.maxScrollExtent - 200 &&
        !_isLoadingMore &&
        _hasMore) {
      _fetchMoreLogs();
    }
  }

  Future<void> _fetchLogs() async {
    final uid = LocalStorageService.currentUserId;
    if (uid == null) {
      setState(() => _isLoading = false);
      return;
    }

    try {
      final response = await _cycleService.getCycleHistory(uid, offset: 0, limit: _limit);
      if (mounted) {
        setState(() {
          _logs = List<Map<String, dynamic>>.from(response['entries'] ?? []);
          _hasMore = response['page']['hasMore'] ?? false;
          _offset = _logs.length;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _fetchMoreLogs() async {
    final uid = LocalStorageService.currentUserId;
    if (uid == null) return;

    setState(() => _isLoadingMore = true);

    try {
      final response = await _cycleService.getCycleHistory(uid, offset: _offset, limit: _limit);
      if (mounted) {
        setState(() {
          final newLogs = List<Map<String, dynamic>>.from(response['entries'] ?? []);
          _logs.addAll(newLogs);
          _hasMore = response['page']['hasMore'] ?? false;
          _offset += newLogs.length;
          _isLoadingMore = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _isLoadingMore = false);
    }
  }

  Color _getFlowColor(String? flow) {
    switch (flow) {
      case 'none':
        return Colors.grey.shade300;
      case 'light':
        return RhythmaColors.rose.withValues(alpha: 0.5);
      case 'medium':
        return RhythmaColors.rose.withValues(alpha: 0.8);
      case 'heavy':
        return RhythmaColors.rose;
      default:
        return Colors.transparent;
    }
  }

  String _getMoodEmoji(String? mood) {
    switch (mood) {
      case 'happy': return '😊';
      case 'neutral': return '😐';
      case 'sad': return '😔';
      case 'frustrated': return '😤';
      case 'loved': return '🥰';
      default: return '➖';
    }
  }

  void _showDetailBottomSheet(Map<String, dynamic> log, String? cycleHistoryLabel) {
    final startDateStr = log['start_date'] as String?;
    final startDate = startDateStr != null ? DateTime.tryParse(startDateStr) : null;
    
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => _LogDetailSheet(log: log, startDate: startDate, title: cycleHistoryLabel ?? 'Cycle History'),
    );
  }

  @override
  Widget build(BuildContext context) {
    const title = 'Cycle History';
    const noLogs = 'No logs yet';

    return Scaffold(
      backgroundColor: RhythmaColors.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: RhythmaColors.foreground),
        title: Text(
          title,
          style: TextStyle(
            color: RhythmaColors.foreground,
            fontSize: 18,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _logs.isEmpty
              ? Center(
                  child: Text(
                    noLogs,
                    style: TextStyle(color: RhythmaColors.mutedFg),
                  ),
                )
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                  itemCount: _logs.length + (_hasMore ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index == _logs.length) {
                      return const Padding(
                        padding: EdgeInsets.all(20),
                        child: Center(child: CircularProgressIndicator()),
                      );
                    }

                    final log = _logs[index];
                    final isLast = index == _logs.length - 1 && !_hasMore;
                    final cycleLength = log['cycle_length'] as int?;
                    final flow = log['flow_intensity'] as String?;
                    final mood = log['mood'] as String?;
                    final symptoms = (log['symptoms'] as List?)?.length ?? 0;
                    final sleepHours = log['sleep_hours'];
                    final stressLevel = log['stress_level'];

                    final startDateStr = log['start_date'] as String?;
                    final startDate = startDateStr != null ? DateTime.tryParse(startDateStr) : null;
                    final dateFormatted = startDate != null ? DateFormat('MMM d, yyyy').format(startDate) : '';

                    return GestureDetector(
                      onTap: () => _showDetailBottomSheet(log, title),
                      child: IntrinsicHeight(
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            // Timeline line
                            SizedBox(
                              width: 24,
                              child: Column(
                                children: [
                                  Container(
                                    width: 12,
                                    height: 12,
                                    margin: const EdgeInsets.only(top: 24),
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: RhythmaColors.primary.withValues(alpha: 0.2),
                                      border: Border.all(color: RhythmaColors.primary, width: 2),
                                    ),
                                  ),
                                  if (!isLast)
                                    Expanded(
                                      child: Container(
                                        width: 2,
                                        color: RhythmaColors.border,
                                      ),
                                    ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 16),
                            
                            // Card
                            Expanded(
                              child: Padding(
                                padding: const EdgeInsets.only(bottom: 16),
                                child: GlassCard(
                                  padding: const EdgeInsets.all(16),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Text(
                                            dateFormatted,
                                            style: TextStyle(
                                              fontWeight: FontWeight.w600,
                                              fontSize: 15,
                                              color: RhythmaColors.foreground,
                                            ),
                                          ),
                                          if (cycleLength != null)
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                              decoration: BoxDecoration(
                                                color: RhythmaColors.surfaceMuted,
                                                borderRadius: BorderRadius.circular(12),
                                              ),
                                              child: Text(
                                                '$cycleLength days',
                                                style: TextStyle(
                                                  fontSize: 11,
                                                  fontWeight: FontWeight.w600,
                                                  color: RhythmaColors.mutedFg,
                                                ),
                                              ),
                                            ),
                                        ],
                                      ),
                                      const SizedBox(height: 12),
                                      Wrap(
                                        spacing: 12,
                                        runSpacing: 8,
                                        children: [
                                          if (flow != null && flow != 'none')
                                            Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Container(
                                                  width: 10,
                                                  height: 10,
                                                  decoration: BoxDecoration(
                                                    shape: BoxShape.circle,
                                                    color: _getFlowColor(flow),
                                                  ),
                                                ),
                                                const SizedBox(width: 4),
                                                Text(flow.toUpperCase(), style: TextStyle(fontSize: 11, color: RhythmaColors.mutedFg, fontWeight: FontWeight.w600)),
                                              ],
                                            ),
                                          if (mood != null)
                                            Text(_getMoodEmoji(mood), style: const TextStyle(fontSize: 14)),
                                          if (symptoms > 0)
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                              decoration: BoxDecoration(
                                                color: RhythmaColors.teal.withValues(alpha: 0.1),
                                                borderRadius: BorderRadius.circular(8),
                                              ),
                                              child: Text(
                                                '$symptoms symp.',
                                                style: const TextStyle(fontSize: 10, color: RhythmaColors.teal, fontWeight: FontWeight.bold),
                                              ),
                                            ),
                                          if (sleepHours != null)
                                            Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Icon(Icons.bedtime_outlined, size: 12, color: RhythmaColors.primary),
                                                const SizedBox(width: 2),
                                                Text('$sleepHours h', style: TextStyle(fontSize: 11, color: RhythmaColors.mutedFg)),
                                              ],
                                            ),
                                          if (stressLevel != null)
                                            Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Icon(Icons.bolt_rounded, size: 12, color: RhythmaColors.teal),
                                                const SizedBox(width: 2),
                                                Text('Lv $stressLevel', style: TextStyle(fontSize: 11, color: RhythmaColors.mutedFg)),
                                              ],
                                            ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}

class _LogDetailSheet extends StatelessWidget {
  final Map<String, dynamic> log;
  final DateTime? startDate;
  final String title;

  const _LogDetailSheet({required this.log, this.startDate, required this.title});

  @override
  Widget build(BuildContext context) {
    final dateFormatted = startDate != null ? DateFormat('MMMM d, yyyy').format(startDate!) : '';
    
    return Container(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 40),
      decoration: BoxDecoration(
        color: RhythmaColors.background,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: RhythmaColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              dateFormatted,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: RhythmaColors.foreground,
              ),
            ),
            const SizedBox(height: 24),
            if (log['flow_intensity'] != null)
              _DetailRow(icon: Icons.water_drop_outlined, label: 'Flow', value: log['flow_intensity'], color: RhythmaColors.rose),
            if (log['mood'] != null)
              _DetailRow(icon: Icons.sentiment_satisfied_alt_rounded, label: 'Mood', value: log['mood'], color: RhythmaColors.coral),
            if (log['stress_level'] != null)
              _DetailRow(icon: Icons.bolt_rounded, label: 'Energy/Stress', value: 'Level ${log['stress_level']}', color: RhythmaColors.teal),
            if (log['sleep_hours'] != null)
              _DetailRow(icon: Icons.bedtime_outlined, label: 'Sleep', value: '${log['sleep_hours']} hours', color: RhythmaColors.primary),
            if (log['symptoms'] != null && (log['symptoms'] as List).isNotEmpty)
              _DetailRow(icon: Icons.psychology_outlined, label: 'Symptoms', value: (log['symptoms'] as List).join(', '), color: RhythmaColors.teal),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;

  const _DetailRow({required this.icon, required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(width: 14),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: TextStyle(fontSize: 12, color: RhythmaColors.mutedFg)),
              Text(value.toString().toUpperCase(), style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: RhythmaColors.foreground)),
            ],
          ),
        ],
      ),
    );
  }
}
