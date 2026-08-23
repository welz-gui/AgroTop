import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

class StoredTokens {
  const StoredTokens({required this.accessToken, required this.refreshToken});

  final String accessToken;
  final String refreshToken;
}

abstract interface class TokenStore {
  Future<StoredTokens?> read();
  Future<void> write(StoredTokens tokens);
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
  const LoginResult(this.user);

  final SessionUser user;
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
  StoredTokens? _tokens;

  Future<bool> restoreSession() async {
    _tokens = await tokenStore.read();
    return _tokens != null;
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
    final tokens = StoredTokens(
      accessToken: body['access_token'] as String,
      refreshToken: body['refresh_token'] as String,
    );
    _tokens = tokens;
    await tokenStore.write(tokens);
    return LoginResult(
      SessionUser.fromJson(body['user'] as Map<String, dynamic>),
    );
  }

  Future<List<AnimalSummary>> listAnimals({
    int skip = 0,
    int limit = 50,
    String status = 'ativo',
  }) async {
    final uri = Uri.parse('$baseUrl/animais').replace(
      queryParameters: {'skip': '$skip', 'limit': '$limit', 'status': status},
    );
    final response = await _authorized(
      (headers) => _http.get(uri, headers: headers),
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
    final response = await _authorized(
      (headers) => _http.get(
        Uri.parse('$baseUrl/animais/${Uri.encodeComponent(id)}'),
        headers: headers,
      ),
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

  Future<WeighingResult> registerWeighing(
    String animalId, {
    required double peso,
    required String data,
    String method = 'pesado',
    String notes = '',
  }) async {
    final response = await _authorized(
      (headers) => _http.post(
        Uri.parse('$baseUrl/animais/${Uri.encodeComponent(animalId)}/pesagens'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({
          'peso': peso,
          'data': data,
          'method': method,
          'notes': notes,
        }),
      ),
    );
    final body = _decode(response);
    if (response.statusCode != 201) {
      throw ApiException(
        _message(body, 'Não foi possível registrar a pesagem.'),
        statusCode: response.statusCode,
      );
    }
    return WeighingResult.fromJson(body as Map<String, dynamic>);
  }

  Future<List<LoteSummary>> listLotes() async {
    final response = await _authorized(
      (headers) => _http.get(Uri.parse('$baseUrl/lotes'), headers: headers),
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw ApiException(
        _message(body, 'Não foi possível carregar os piquetes.'),
        statusCode: response.statusCode,
      );
    }
    return (body as List<dynamic>)
        .map((item) => LoteSummary.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<MovementResult> moveAnimals({
    required List<String> animalIds,
    required String toLoteId,
    required String movementDate,
    String? reason = 'manejo',
    String? notes,
  }) async {
    final response = await _authorized(
      (headers) => _http.post(
        Uri.parse('$baseUrl/animais/movimentar'),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({
          'animal_ids': animalIds,
          'to_lote_id': toLoteId,
          'movement_date': movementDate,
          'reason': reason,
          'notes': notes,
        }),
      ),
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw ApiException(
        _message(body, 'Não foi possível movimentar os animais.'),
        statusCode: response.statusCode,
      );
    }
    return MovementResult.fromJson(body as Map<String, dynamic>);
  }

  Future<List<ProtocoloSummary>> listProtocolos({String? animalId}) async {
    final uri = Uri.parse('$baseUrl/protocolos').replace(
      queryParameters: animalId == null ? null : {'animal_id': animalId},
    );
    final response = await _authorized(
      (headers) => _http.get(uri, headers: headers),
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw ApiException(
        _message(body, 'Não foi possível carregar os protocolos.'),
        statusCode: response.statusCode,
      );
    }
    return (body as List<dynamic>)
        .map((item) => ProtocoloSummary.fromJson(item as Map<String, dynamic>))
        .toList(growable: false);
  }

  Future<AnimalMedications> getAnimalMedications(String animalId) async {
    final response = await _authorized(
      (headers) => _http.get(
        Uri.parse(
          '$baseUrl/animais/${Uri.encodeComponent(animalId)}/medicamentos',
        ),
        headers: headers,
      ),
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      throw ApiException(
        _message(body, 'Não foi possível carregar as informações de sanidade.'),
        statusCode: response.statusCode,
      );
    }
    return AnimalMedications.fromJson(body as Map<String, dynamic>);
  }

  Future<String?> registerMedication(
    String animalId, {
    required String medicamento,
    required double dose,
    required String unidade,
    required String via,
    required int carenciaDias,
    required String data,
    int? protocoloId,
    String? notas,
  }) async {
    final response = await _authorized(
      (headers) => _http.post(
        Uri.parse(
          '$baseUrl/animais/${Uri.encodeComponent(animalId)}/medicamentos',
        ),
        headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({
          'medicamento': medicamento,
          'dose': dose,
          'unidade': unidade,
          'via': via,
          'carencia_dias': carenciaDias,
          'data': data,
          'protocolo_id': protocoloId,
          'notas': notas,
        }),
      ),
    );
    final body = _decode(response);
    if (response.statusCode != 201) {
      throw ApiException(
        _message(body, 'Não foi possível registrar o medicamento.'),
        statusCode: response.statusCode,
      );
    }
    return body is Map<String, dynamic>
        ? body['carencia_ate'] as String?
        : null;
  }

  Future<void> logout() async {
    final tokens = _tokens ?? await tokenStore.read();
    try {
      if (tokens != null) {
        await _http.post(
          Uri.parse('$baseUrl/auth/logout'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({'refresh_token': tokens.refreshToken}),
        );
      }
    } finally {
      _tokens = null;
      await tokenStore.clear();
    }
  }

  Future<http.Response> _authorized(
    Future<http.Response> Function(Map<String, String> headers) send,
  ) async {
    var tokens = await _requireTokens();
    var response = await send({
      'Authorization': 'Bearer ${tokens.accessToken}',
    });
    if (response.statusCode != 401) return response;

    tokens = await _refresh(tokens.refreshToken);
    response = await send({'Authorization': 'Bearer ${tokens.accessToken}'});
    if (response.statusCode == 401) {
      _tokens = null;
      await tokenStore.clear();
    }
    return response;
  }

  Future<StoredTokens> _requireTokens() async {
    _tokens ??= await tokenStore.read();
    if (_tokens == null) {
      throw const ApiException(
        'Sessão ausente. Entre novamente.',
        statusCode: 401,
      );
    }
    return _tokens!;
  }

  Future<StoredTokens> _refresh(String refreshToken) async {
    final response = await _http.post(
      Uri.parse('$baseUrl/auth/refresh'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh_token': refreshToken}),
    );
    final body = _decode(response);
    if (response.statusCode != 200) {
      _tokens = null;
      await tokenStore.clear();
      throw ApiException(
        _message(body, 'Sessão expirada. Entre novamente.'),
        statusCode: response.statusCode,
      );
    }
    final tokens = StoredTokens(
      accessToken: body['access_token'] as String,
      refreshToken: refreshToken,
    );
    _tokens = tokens;
    await tokenStore.write(tokens);
    return tokens;
  }

  dynamic _decode(http.Response response) {
    if (response.bodyBytes.isEmpty) return null;
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
    if (body is! Map<String, dynamic>) return fallback;
    final detail = body['detail'];
    if (detail is String) return detail;
    if (detail is List && detail.isNotEmpty && detail.first is Map) {
      final message = (detail.first as Map)['msg'];
      if (message is String) return message;
    }
    return fallback;
  }
}
