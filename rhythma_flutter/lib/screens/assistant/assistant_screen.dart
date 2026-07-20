import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import '../../config/theme.dart';
import '../../services/local_storage_service.dart';
import '../../providers/theme_provider.dart';
import '../../services/assistant_service.dart';

class AssistantScreen extends StatefulWidget {
  const AssistantScreen({super.key});
  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends State<AssistantScreen> {
  final TextEditingController _ctrl = TextEditingController();
  final ScrollController _scroll = ScrollController();
  bool _isLoading = false;

  late List<String> _suggested;
  late List<_Msg> _messages;
  bool _initialized = false;

  // The welcome strings are translated per-language but still contain the
  // placeholder demo name "Aarya" (or its transliteration). Swap it for the
  // signed-in user's actual profile name where we can.
  static const Map<String, String> _placeholderNames = {
    'en': 'Aarya',
    'hi': 'आर्या',
    'mr': 'आर्या',
    'ta': 'ஆர்யா',
    'te': 'ఆర్య',
  };

  String _personalizedWelcome(String rawWelcome) {
    final placeholder =
        _placeholderNames[LocalStorageService.preferredLanguage];
    final name = (LocalStorageService.getProfile()?['name'] as String?)?.trim();
    if (placeholder == null) return rawWelcome;
    final displayName = (name != null && name.isNotEmpty) ? name : 'User';
    return rawWelcome.replaceFirst(placeholder, displayName);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      final l10n = AppLocalizations.of(context)!;
      _suggested = [
        l10n.assistantSug1,
        l10n.assistantSug2,
        l10n.assistantSug3,
        l10n.assistantSug4,
        l10n.assistantSug5,
      ];

      final saved = LocalStorageService.getChatHistory();
      final restored = saved
          .map((m) => _Msg(
                role: m['role'] ?? 'model',
                content: m['content'] ?? '',
                isError: m['isError'] == 'true',
              ))
          // Older/corrupted entries can have an empty `content` (e.g. from
          // a previous chat-history schema, or an interrupted save) and
          // rendered as blank, outline-only bubbles with no visible text.
          // Drop those rather than showing dead bubbles forever.
          .where((m) => m.content.trim().isNotEmpty)
          .toList();

      if (restored.isNotEmpty) {
        _messages = restored;
      } else {
        _messages = [
          _Msg(
              role: 'model',
              content: _personalizedWelcome(l10n.assistantWelcome)),
        ];
      }
      _initialized = true;

      // If we actually dropped any blank entries, persist the cleaned-up
      // list so this doesn't need to re-filter (or show a brief flash of
      // the blank bubbles) on every future load.
      if (restored.length != saved.length) {
        _persistHistory();
      }
    }
  }

  Future<void> _persistHistory() async {
    await LocalStorageService.saveChatHistory(
      _messages
          .map((m) => {
                'role': m.role,
                'content': m.content,
                'isError': m.isError.toString(),
              })
          .toList(),
    );
  }

  Future<void> _send(String text) async {
    final t = text.trim();
    if (t.isEmpty || _isLoading) return;

    // Build conversation context from what's already on screen so the
    // assistant can answer follow-up questions, not just isolated ones.
    // _Msg already uses the same role/content vocabulary as the backend's
    // ChatMessage model, so no translation is needed here.
    final history = _messages
        .where((m) => !m.isError)
        .toList()
        .reversed
        .take(10)
        .toList()
        .reversed
        .map((m) => {'role': m.role, 'content': m.content})
        .toList();

    setState(() {
      _messages.add(_Msg(role: 'user', content: t));
      _isLoading = true;
    });
    _ctrl.clear();
    _scrollToBottom();

    try {
      final assistant = AssistantService();
      final responseText = await assistant.chat(
        t,
        language: LocalStorageService.preferredLanguage,
        history: history,
      );
      setState(() {
        _isLoading = false;
        _messages.add(_Msg(role: 'model', content: responseText));
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _messages.add(_Msg(
            role: 'model', content: 'Error: ${e.toString()}', isError: true));
      });
    }
    _scrollToBottom();
    await _persistHistory();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 80), () {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent + 200,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    context.watch<ThemeProvider>();
    final l10n = AppLocalizations.of(context)!;
    final lang = LocalStorageService.preferredLanguage;

    //  Wrapped in Scaffold
    return Scaffold(
      backgroundColor: RhythmaColors.background,
      appBar: AppBar(
        title: Text(l10n.assistantTitle),
        backgroundColor: RhythmaColors.surface,
        elevation: 0,
      ),
      body: Column(
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                      gradient: RhythmaGradients.primary,
                      shape: BoxShape.circle),
                  child: const Icon(Icons.favorite_rounded,
                      color: Colors.white, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(l10n.assistantTitle,
                            style: TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.w700,
                                color: RhythmaColors.foreground)),
                        Text(l10n.assistantSubtitle,
                            style: TextStyle(
                                fontSize: 12, color: RhythmaColors.mutedFg)),
                      ]),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: RhythmaColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(lang.toUpperCase(),
                      style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: RhythmaColors.primary)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),

          // Chat list
          Expanded(
            child: ListView.builder(
              controller: _scroll,
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              itemCount: _messages.length + (_isLoading ? 1 : 0),
              itemBuilder: (ctx, i) {
                if (_isLoading && i == _messages.length) return _TypingBubble();
                return _ChatBubble(msg: _messages[i]);
              },
            ),
          ),

          // Suggested chips (only before first user message)
          if (_messages.length == 1)
            SizedBox(
              height: 38,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: _suggested.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (_, i) => GestureDetector(
                  onTap: () => _send(_suggested[i]),
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    decoration: BoxDecoration(
                      color: RhythmaColors.surfaceMuted,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: RhythmaColors.border),
                    ),
                    child: Text(_suggested[i],
                        style: TextStyle(
                            fontSize: 12, color: RhythmaColors.foreground)),
                  ),
                ),
              ),
            ),
          const SizedBox(height: 8),

          // Input bar – this TextField now has a Material ancestor (Scaffold)
          // Extra bottom padding keeps this clear of the floating bottom nav
          // pill (which overlaps the body because the shell uses
          // extendBody: true), so it doesn't sit underneath — and become
          // untappable behind — the nav bar.
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 96),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(28),
              child: Container(
                decoration: BoxDecoration(
                  color: RhythmaColors.surface.withOpacity(0.85),
                  borderRadius: BorderRadius.circular(28),
                  border: Border.all(
                      color: RhythmaColors.lavender.withOpacity(0.5)),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _ctrl,
                        style: TextStyle(
                            fontSize: 14, color: RhythmaColors.foreground),
                        decoration: InputDecoration(
                          hintText: l10n.assistantInputHint,
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(
                              horizontal: 20, vertical: 14),
                        ),
                        onSubmitted: _send,
                        textInputAction: TextInputAction.send,
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: GestureDetector(
                        onTap: _isLoading ? null : () => _send(_ctrl.text),
                        child: Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            gradient:
                                _isLoading ? null : RhythmaGradients.primary,
                            color: _isLoading
                                ? RhythmaColors.mutedFg.withOpacity(0.25)
                                : null,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.send_rounded,
                              color: Colors.white, size: 18),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Helper widgets ──────────────────────────────────────────────

/// Canonical local message shape — deliberately mirrors the backend's
/// `ChatMessage` model (role: "user" | "model", content: String) so the
/// same vocabulary is used end-to-end: in widget state, in on-device
/// persistence, and in the API request/response. Previously this used
/// "ai"/"text" locally while the backend used "model"/"content", requiring
/// a translation layer between the two — that mismatch is now removed.
class _Msg {
  final String role;
  final String content;
  final bool isError;
  const _Msg({required this.role, required this.content, this.isError = false});
}

class _ChatBubble extends StatelessWidget {
  final _Msg msg;
  const _ChatBubble({required this.msg});
  @override
  Widget build(BuildContext context) {
    final isUser = msg.role == 'user';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (!isUser) ...[
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                  gradient: RhythmaGradients.primary, shape: BoxShape.circle),
              child: const Icon(Icons.favorite_rounded,
                  color: Colors.white, size: 14),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                gradient: isUser ? RhythmaGradients.primary : null,
                color: isUser
                    ? null
                    : msg.isError
                        ? Colors.red.withOpacity(0.08)
                        : RhythmaColors.surface.withOpacity(0.85),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(18),
                  topRight: const Radius.circular(18),
                  bottomLeft: Radius.circular(isUser ? 18 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 18),
                ),
                border: isUser
                    ? null
                    : Border.all(
                        color: msg.isError
                            ? Colors.red.withOpacity(0.3)
                            : RhythmaColors.lavender.withOpacity(0.4),
                      ),
              ),
              child: isUser
                  ? Text(msg.content,
                      style: const TextStyle(
                          fontSize: 14, height: 1.5, color: Colors.white))
                  : _FormattedMessage(
                      text: msg.content,
                      color: msg.isError
                          ? Colors.red.shade700
                          : RhythmaColors.foreground,
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Renders a subset of markdown (bold text and bullet lists) that the
/// assistant commonly returns, instead of showing the raw `**`/`*` markers.
class _FormattedMessage extends StatelessWidget {
  final String text;
  final Color color;
  const _FormattedMessage({required this.text, required this.color});

  static final _boldPattern = RegExp(r'\*\*(.+?)\*\*');

  List<InlineSpan> _parseInline(String line, TextStyle base) {
    final spans = <InlineSpan>[];
    int last = 0;
    for (final match in _boldPattern.allMatches(line)) {
      if (match.start > last) {
        spans.add(
            TextSpan(text: line.substring(last, match.start), style: base));
      }
      spans.add(TextSpan(
        text: match.group(1),
        style: base.copyWith(fontWeight: FontWeight.w700),
      ));
      last = match.end;
    }
    if (last < line.length) {
      spans.add(TextSpan(text: line.substring(last), style: base));
    }
    return spans;
  }

  @override
  Widget build(BuildContext context) {
    final base = TextStyle(fontSize: 14, height: 1.5, color: color);
    final lines = text.split('\n');
    final children = <Widget>[];

    for (final rawLine in lines) {
      final line = rawLine.trimRight();
      if (line.trim().isEmpty) {
        children.add(const SizedBox(height: 6));
        continue;
      }
      final bulletMatch = RegExp(r'^\s*\*\s+(.*)$').firstMatch(line);
      if (bulletMatch != null) {
        children.add(Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('•  ', style: base),
              Expanded(
                child: Text.rich(
                  TextSpan(children: _parseInline(bulletMatch.group(1)!, base)),
                ),
              ),
            ],
          ),
        ));
      } else {
        children.add(Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Text.rich(TextSpan(children: _parseInline(line, base))),
        ));
      }
    }

    return Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }
}

class _TypingBubble extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(children: [
        Container(
          width: 28,
          height: 28,
          decoration: BoxDecoration(
              gradient: RhythmaGradients.primary, shape: BoxShape.circle),
          child:
              const Icon(Icons.favorite_rounded, color: Colors.white, size: 14),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            color: RhythmaColors.surface.withOpacity(0.85),
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(18),
              topRight: Radius.circular(18),
              bottomRight: Radius.circular(18),
              bottomLeft: Radius.circular(4),
            ),
            border: Border.all(color: RhythmaColors.lavender.withOpacity(0.4)),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            _dot(0),
            const SizedBox(width: 4),
            _dot(150),
            const SizedBox(width: 4),
            _dot(300),
          ]),
        ),
      ]),
    );
  }

  Widget _dot(int delay) => _AnimatedDot(delay: delay);
}

class _AnimatedDot extends StatefulWidget {
  final int delay;
  const _AnimatedDot({required this.delay});
  @override
  State<_AnimatedDot> createState() => _AnimatedDotState();
}

class _AnimatedDotState extends State<_AnimatedDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;
  late final Animation<double> _a;
  @override
  void initState() {
    super.initState();
    _c = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600))
      ..repeat(reverse: true);
    _a = CurvedAnimation(parent: _c, curve: Curves.easeInOut);
    Future.delayed(Duration(milliseconds: widget.delay), () {
      if (mounted) _c.forward();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FadeTransition(
        opacity: _a,
        child: Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
                color: RhythmaColors.primary, shape: BoxShape.circle)),
      );
}
