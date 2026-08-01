import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

abstract interface class TokenStore {
  Future<String?> read();
  Future<void> write(String token);
  Future<void> clear();
}

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
  @override
  String toString() => message;
}

class LoginResult {
  const LoginResult(this.user, this.token);
  final SessionUser user;
  final String token;
}

class ApiClient {
  ApiClient({
    required this.tokenStore,
    http.Client? httpClient,
    String? baseUrl,
  }) : _http = httpClient ?? http.Client(),
       baseUrl =
           baseUrl ??
           const String.fromEnvironment(
             'AGROTOP_API_URL',
             defaultValue: 'http://10.0.2.2:8000',
           );

  final TokenStore tokenStore;
  final http.Client _http;
  final String baseUrl;
  String? _token;

  Future<bool> restoreSession() async {
    _token = await tokenStore.read();
    return _token != null;
  }

  Future<LoginResult> login(String username, String password) async {
    final response = await _http.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw ApiException(
        _message(body, 'Não foi possível entrar.'),
        statusCode: response.statusCode,
      );
    }
    _token = body['access_token'] as String;
    await tokenStore.write(_token!);
    return LoginResult(
      SessionUser.fromJson(body['user'] as Map<String, dynamic>),
      _token!,
    );
  }

  Future<List<AnimalSummary>> listAnimals() async {
    final response = await _http.get(
      Uri.parse('$baseUrl/animais'),
      headers: await _authHeaders(),
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw ApiException(
        _message(body, 'Não foi possível carregar os animais.'),
        statusCode: response.statusCode,
      );
    }
    return (body as List<dynamic>)
        .map((item) => AnimalSummary.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<AnimalDetail> getAnimal(String id) async {
    final response = await _http.get(
      Uri.parse('$baseUrl/animais/${Uri.encodeComponent(id)}'),
      headers: await _authHeaders(),
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw ApiException(
        _message(body, 'Não foi possível carregar a ficha.'),
        statusCode: response.statusCode,
      );
    }
    return AnimalDetail.fromJson(body as Map<String, dynamic>);
  }

  Future<void> logout() async {
    _token = null;
    await tokenStore.clear();
  }

  Future<Map<String, String>> _authHeaders() async {
    _token ??= await tokenStore.read();
    if (_token == null) {
      throw const ApiException(
        'Sessão ausente. Entre novamente.',
        statusCode: 401,
      );
    }
    return {'Authorization': 'Bearer $_token'};
  }

  dynamic _decode(http.Response response) {
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiException(
        'A API respondeu em formato inválido.',
        statusCode: response.statusCode,
      );
    }
  }

  String _message(dynamic body, String fallback) {
    if (body is Map<String, dynamic> && body['detail'] is String) {
      return body['detail'] as String;
    }
    return fallback;
  }
}
