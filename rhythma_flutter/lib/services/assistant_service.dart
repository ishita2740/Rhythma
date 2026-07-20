import 'package:dio/dio.dart';
import 'api_client.dart';

class AssistantService {
  final Dio _dio = ApiClient.dio;

  Future<String> chat(
    String message, {
    String language = 'en',
    List<Map<String, String>> history = const [],
  }) async {
    try {
      final response = await _dio.post(
        '/assistant/chat',
        data: {
          'message': message,
          'language': language,
          'history': history,
        },
      );
      final data = response.data;
      if (data is Map<String, dynamic>) {
        final reply = data['response'];
        if (reply is String && reply.trim().isNotEmpty) return reply;
      }
      throw const AssistantException(
          'The assistant returned an empty response.');
    } on DioException catch (e) {
      throw AssistantException(
          _readErrorMessage(e, 'Failed to get a response. Please try again.'));
    }
  }

  Future<List<Map<String, String>>> getLanguages() async {
    try {
      final response = await _dio.get('/assistant/languages');
      final List data = response.data;
      return data.map((e) => Map<String, String>.from(e)).toList();
    } on DioException catch (e) {
      throw AssistantException(
          _readErrorMessage(e, 'Failed to load languages.'));
    }
  }

  String _readErrorMessage(DioException error, String fallback) {
    if (error.response?.statusCode == 401) {
      return 'Your session expired. Please log in again.';
    }
    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.connectionError) {
      return 'Connection error. Please check your internet and try again.';
    }

    final data = error.response?.data;
    if (data is Map<String, dynamic>) {
      final detail = data['detail'];
      if (detail is String && detail.trim().isNotEmpty) return detail;
    }

    if (error.response?.statusCode != null &&
        error.response!.statusCode! >= 500) {
      return 'The assistant is temporarily unavailable. Please try again later.';
    }

    return fallback;
  }
}

class AssistantException implements Exception {
  final String message;

  const AssistantException(this.message);

  @override
  String toString() => message;
}
