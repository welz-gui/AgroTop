import 'dart:convert';
import 'dart:io';

class MockApiServer {
  MockApiServer._(this._server) {
    _server.listen(_handle);
  }

  final HttpServer _server;
  double currentWeight = 382.4;
  int refreshRequests = 0;
  int listRequests = 0;
  int detailRequests = 0;
  int weighingRequests = 0;

  String get baseUrl => 'http://${_server.address.address}:${_server.port}';

  static Future<MockApiServer> start() async =>
      MockApiServer._(await HttpServer.bind(InternetAddress.loopbackIPv4, 0));

  Future<void> close() => _server.close(force: true);

  Future<void> _handle(HttpRequest request) async {
    try {
      final path = request.uri.path;
      if (request.method == 'POST' && path == '/auth/login') {
        final body = await _body(request);
        if (body['username'] != 'admin' || body['password'] != 'senha-segura') {
          await _json(request, 401, {'detail': 'Credenciais inválidas'});
          return;
        }
        await _json(request, 200, {
          'access_token': 'access-expired',
          'token_type': 'bearer',
          'expires_in': 900,
          'refresh_token': 'refresh-valid',
          'user': {
            'id': 1,
            'username': 'admin',
            'name': 'Administrador',
            'role': 'admin',
          },
        });
        return;
      }
      if (request.method == 'POST' && path == '/auth/refresh') {
        refreshRequests++;
        final body = await _body(request);
        if (body['refresh_token'] != 'refresh-valid') {
          await _json(request, 401, {'detail': 'Refresh token inválido'});
          return;
        }
        await _json(request, 200, {
          'access_token': 'access-live',
          'token_type': 'bearer',
          'expires_in': 900,
        });
        return;
      }
      if (request.method == 'POST' && path == '/auth/logout') {
        final body = await _body(request);
        if (body['refresh_token'] != 'refresh-valid') {
          await _json(request, 401, {'detail': 'Refresh token inválido'});
          return;
        }
        request.response.statusCode = 204;
        await request.response.close();
        return;
      }

      if (request.headers.value(HttpHeaders.authorizationHeader) !=
          'Bearer access-live') {
        await _json(request, 401, {'detail': 'Token inválido ou expirado'});
        return;
      }

      if (request.method == 'GET' && path == '/animais') {
        listRequests++;
        if (request.uri.queryParameters['skip'] != '0' ||
            request.uri.queryParameters['limit'] != '50' ||
            request.uri.queryParameters['status'] != 'ativo') {
          await _json(request, 422, {
            'detail': [
              {
                'loc': ['query'],
                'msg': 'Paginação inválida',
                'type': 'value_error',
              },
            ],
          });
          return;
        }
        await _json(request, 200, [_animal()]);
        return;
      }
      if (request.method == 'GET' && path == '/animais/BR0001') {
        detailRequests++;
        await _json(request, 200, {
          ..._animal(),
          'entry_date': '2026-01-10',
          'fornecedor_id': 7,
          'fornecedor_name': 'Fazenda Boa Vista',
          'gmd_recent_kg_day': 0.742,
          'gmd_total_kg_day': 0.513,
        });
        return;
      }
      if (request.method == 'POST' && path == '/animais/BR0001/pesagens') {
        weighingRequests++;
        final body = await _body(request);
        final expectedKeys = {'peso', 'data', 'method', 'notes'};
        if (body.keys.toSet().difference(expectedKeys).isNotEmpty ||
            expectedKeys.difference(body.keys.toSet()).isNotEmpty) {
          await _json(request, 422, {
            'detail': [
              {
                'loc': ['body'],
                'msg': 'Payload inválido',
                'type': 'value_error',
              },
            ],
          });
          return;
        }
        currentWeight = (body['peso'] as num).toDouble();
        await _json(request, 201, {
          'status': 'success',
          'message': 'Pesagem registrada com sucesso.',
          'animal_id': 'BR0001',
          'peso': currentWeight,
          'data': body['data'],
        });
        return;
      }
      await _json(request, 404, {'detail': 'Não encontrado'});
    } catch (_) {
      try {
        await _json(request, 500, {'detail': 'Erro no servidor mock'});
      } catch (_) {
        await request.response.close();
      }
    }
  }

  Map<String, dynamic> _animal() => {
    'id': 'BR0001',
    'breed': 'Nelore',
    'sex': 'M',
    'birth_date': '2024-03-10',
    'entry_weight': 278.2,
    'current_weight': currentWeight,
    'target_weight': 500.0,
    'status': 'ativo',
    'lote_id': 'P01',
    'lot_name': 'Piquete Central',
    'animal_uuid': '123e4567-e89b-12d3-a456-426614174000',
  };

  Future<Map<String, dynamic>> _body(HttpRequest request) async {
    final raw = await utf8.decoder.bind(request).join();
    return jsonDecode(raw) as Map<String, dynamic>;
  }

  Future<void> _json(HttpRequest request, int status, Object body) async {
    request.response.statusCode = status;
    request.response.headers.contentType = ContentType.json;
    request.response.write(jsonEncode(body));
    await request.response.close();
  }
}
