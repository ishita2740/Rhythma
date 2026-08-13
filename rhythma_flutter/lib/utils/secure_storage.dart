import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorage {
  static const _storage = FlutterSecureStorage();
  static const _tokenKey = 'jwt_token';
  static const _refreshTokenKey = 'jwt_refresh_token';

  // ─── Access Token ──────────────────────────────────────────────────────

  static Future<void> saveToken(String token) async {
    await _storage.write(key: _tokenKey, value: token);
  }

  static Future<String?> getToken() async {
    return await _storage.read(key: _tokenKey);
  }

  static Future<void> deleteToken() async {
    await _storage.delete(key: _tokenKey);
  }

  static Future<bool> hasToken() async {
    return await _storage.read(key: _tokenKey) != null;
  }

  // ─── Refresh Token ─────────────────────────────────────────────────────

  static Future<void> saveRefreshToken(String token) async {
    await _storage.write(key: _refreshTokenKey, value: token);
  }

  static Future<String?> getRefreshToken() async {
    return await _storage.read(key: _refreshTokenKey);
  }

  static Future<void> deleteRefreshToken() async {
    await _storage.delete(key: _refreshTokenKey);
  }

  static Future<bool> hasRefreshToken() async {
    return await _storage.read(key: _refreshTokenKey) != null;
  }

  // ─── Clear All Auth State ──────────────────────────────────────────────

  static Future<void> clearAuth() async {
    await Future.wait([
      deleteToken(),
      deleteRefreshToken(),
    ]);
  }
}
