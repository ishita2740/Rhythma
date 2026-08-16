import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:rhythma/services/api_client.dart';

/// A canned JSON response served by [MockDioAdapter].
class MockDioResponse {
  final int statusCode;
  final Map<String, dynamic>? data;

  const MockDioResponse(this.statusCode, [this.data]);
}

/// Replaces [ApiClient.dio]'s HTTP client with one that serves canned JSON
/// responses, so widget/unit tests never touch the network. The handler
/// receives the [RequestOptions] so tests can branch on path/method.
class MockDioAdapter implements HttpClientAdapter {
  MockDioAdapter(this._handler);

  final MockDioResponse Function(RequestOptions options) _handler;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final response = _handler(options);
    return ResponseBody.fromString(
      response.data != null ? jsonEncode(response.data) : '',
      response.statusCode,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

/// Installs a [MockDioAdapter] that routes every [ApiClient.dio] request
/// through [handler]. Remember to call [restoreDioAdapter] in `tearDown`.
void installMockDioAdapter(
  MockDioResponse Function(RequestOptions options) handler,
) {
  ApiClient.dio.httpClientAdapter = MockDioAdapter(handler);
}

/// Restores the real (flutter_test-stubbed) HTTP client after a test.
void restoreDioAdapter() {
  ApiClient.dio.httpClientAdapter = IOHttpClientAdapter();
}
