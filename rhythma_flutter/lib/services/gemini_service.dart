import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Response from the AI assistant
class AssistantMessage {
  final String text;
  final bool isError;

  const AssistantMessage({required this.text, this.isError = false});
}

/// Thin wrapper around the Gemini API for the multilingual AI assistant.
/// Falls back gracefully to a canned response when the API key is absent
/// (e.g. during UI development / demo runs).
class GeminiService {
  static const _model = 'gemini-1.5-flash';
  static const _baseUrl =
      'https://generativelanguage.googleapis.com/v1beta/models';

  static const _systemPrompt = '''
You are Rhythma, a compassionate AI menstrual health companion designed
specifically for women in India.

Guidelines:
- Respond in the same language the user writes in (Hindi, Marathi, Tamil, English)
- Provide clear, accessible health education about menstrual health, PCOD, hormones
- Use a warm, non-judgmental, supportive tone
- Never diagnose or prescribe; always recommend consulting a doctor for medical decisions
- Be culturally sensitive to Indian contexts
- Keep responses concise — this is a mobile chat interface
- End symptom-related responses with a gentle reminder to consult a healthcare professional
''';

  /// Send a message to Gemini and return the assistant's reply.
  static Future<AssistantMessage> chat({
    required String message,
    List<Map<String, String>> history = const [],
  }) async {
    final apiKey = dotenv.maybeGet('GEMINI_API_KEY');

    // Demo fallback when no API key is configured
    if (apiKey == null || apiKey.isEmpty) {
      return AssistantMessage(
        text:
            "That's a thoughtful question 🌸 Based on typical patterns, slight "
            "variation is normal. Stress, sleep, and nutrition all play a role. "
            "Would you like me to explain what's typical vs. when to consult a doctor?\n\n"
            "⚠️ Connect a Gemini API key in .env to enable real AI responses.",
      );
    }

    try {
      // Build Gemini contents array from history + new message
      final contents = <Map<String, dynamic>>[
        {
          'role': 'user',
          'parts': [{'text': _systemPrompt}],
        },
        {
          'role': 'model',
          'parts': [{'text': 'Understood. I am Rhythma, ready to help.'}],
        },
        for (final msg in history)
          {
            'role': msg['role'] == 'user' ? 'user' : 'model',
            'parts': [{'text': msg['text']}],
          },
        {
          'role': 'user',
          'parts': [{'text': message}],
        },
      ];

      final uri = Uri.parse(
        '$_baseUrl/$_model:generateContent?key=$apiKey',
      );

      final response = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'contents': contents}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final text = data['candidates']?[0]?['content']?['parts']?[0]?['text']
            as String? ??
            'Sorry, I could not generate a response. Please try again.';
        return AssistantMessage(text: text);
      } else {
        debugPrint('Gemini API error ${response.statusCode}: ${response.body}');
        return AssistantMessage(
          text: 'Something went wrong. Please try again in a moment.',
          isError: true,
        );
      }
    } catch (e) {
      debugPrint('GeminiService error: $e');
      return AssistantMessage(
        text: 'Unable to connect. Please check your internet connection.',
        isError: true,
      );
    }
  }
}
