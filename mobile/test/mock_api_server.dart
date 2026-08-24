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
  int movementRequests = 0;
  int protocolosRequests = 0;
  int medicationsRequests = 0;
  int postMedicationRequests = 0;
  String? carenciaAte;
  final List<Map<String, dynamic>> _medications = [];
  Map<String, dynamic>? lastMovementBody;
  Map<String, dynamic>? lastMedicationBody;
  int photoUploadRequests = 0;
  int? lastPhotoUploadSize;
  final Map<int, List<int>> _photos = {};
  final Map<String, String> _animalLotes = {
    'BR0001': 'P01',
    'BR0002': 'P02',
    'BR0003': 'P01',
  };

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
        await _json(
          request,
          200,
          _animalLotes.keys.map(_animal).toList(growable: false),
        );
        return;
      }
      if (request.method == 'GET' &&
          path.startsWith('/animais/') &&
          path.endsWith('/medicamentos')) {
        final id = Uri.decodeComponent(
          path.substring('/animais/'.length, path.length - '/medicamentos'.length),
        );
        if (!_animalLotes.containsKey(id)) {
          await _json(request, 404, {'detail': 'Animal não encontrado'});
          return;
        }
        medicationsRequests++;
        await _json(request, 200, {
          'carencia_ate': carenciaAte,
          'aplicacoes': _medications,
        });
        return;
      }
      if (request.method == 'POST' &&
          path.startsWith('/animais/') &&
          path.endsWith('/medicamentos')) {
        final id = Uri.decodeComponent(
          path.substring('/animais/'.length, path.length - '/medicamentos'.length),
        );
        if (!_animalLotes.containsKey(id)) {
          await _json(request, 404, {'detail': 'Animal não encontrado'});
          return;
        }
        postMedicationRequests++;
        final body = await _body(request);
        lastMedicationBody = body;
        final carenciaDias = (body['carencia_dias'] as num).toInt();
        if (carenciaDias > 0) {
          final dataApp = DateTime.parse(body['data'] as String);
          final carenciaFim = dataApp.add(Duration(days: carenciaDias));
          carenciaAte =
              '${carenciaFim.year.toString().padLeft(4, '0')}-'
              '${carenciaFim.month.toString().padLeft(2, '0')}-'
              '${carenciaFim.day.toString().padLeft(2, '0')}';
        }
        _medications.insert(0, {
          'medicamento': body['medicamento'],
          'dose': (body['dose'] as num).toDouble(),
          'unidade': body['unidade'],
          'via': body['via'],
          'carencia_dias': carenciaDias,
          'data': body['data'],
          'protocolo_id': body['protocolo_id'],
        });
        await _json(request, 201, {'carencia_ate': carenciaAte});
        return;
      }
      if (request.method == 'GET' && path == '/protocolos') {
        protocolosRequests++;
        final animalId = request.uri.queryParameters['animal_id'];
        await _json(request, 200, [
          {
            'id': 1,
            'nome': 'Ivermectina 1%',
            'via': 'Subcutânea',
            'carencia_dias': 28,
            'unidade_dose': 'ml',
            'dose_sugerida': animalId == 'BR0001' ? 7.6 : (animalId != null ? 5.0 : null),
          },
          {
            'id': 2,
            'nome': 'Vacina Aftosa',
            'via': 'Subcutânea',
            'carencia_dias': 0,
            'unidade_dose': 'ml',
            'dose_sugerida': animalId != null ? 2.0 : null,
          },
        ]);
        return;
      }
      if (request.method == 'GET' && path == '/animais/BR0001/fotos') {
        await _json(
          request,
          200,
          _photos.keys
              .toList(growable: false)
              .reversed
              .map(
                (id) => {
                  'id': id,
                  'taken_date': '2026-08-23',
                  'mime': 'image/jpeg',
                },
              )
              .toList(growable: false),
        );
        return;
      }
      if (request.method == 'POST' && path == '/animais/BR0001/fotos') {
        photoUploadRequests++;
        final contentType = request.headers.contentType;
        final boundary = contentType?.parameters['boundary'];
        if (contentType?.mimeType != 'multipart/form-data' ||
            boundary == null) {
          await _json(request, 422, {'detail': 'Multipart inválido'});
          return;
        }
        final raw = await request.fold<List<int>>(
          <int>[],
          (bytes, chunk) => bytes..addAll(chunk),
        );
        final photo = _multipartFile(raw, boundary);
        if (photo == null) {
          await _json(request, 422, {'detail': 'Campo arquivo ausente'});
          return;
        }
        final id = _photos.length + 1;
        _photos[id] = photo;
        lastPhotoUploadSize = photo.length;
        await _json(request, 201, {'id': id});
        return;
      }
      if (request.method == 'GET' && path.startsWith('/fotos/')) {
        final id = int.tryParse(path.substring('/fotos/'.length));
        final bytes = _photos[id];
        if (bytes == null) {
          await _json(request, 404, {'detail': 'Foto não encontrada'});
          return;
        }
        request.response.statusCode = 200;
        request.response.headers.contentType = ContentType('image', 'jpeg');
        request.response.add(bytes);
        await request.response.close();
        return;
      }
      if (request.method == 'GET' && path.startsWith('/animais/')) {
        final id = Uri.decodeComponent(path.substring('/animais/'.length));
        if (!_animalLotes.containsKey(id)) {
          await _json(request, 404, {'detail': 'Animal não encontrado'});
          return;
        }
        detailRequests++;
        await _json(request, 200, {
          ..._animal(id),
          'entry_date': '2026-01-10',
          'fornecedor_id': 7,
          'fornecedor_name': 'Fazenda Boa Vista',
          'gmd_recent_kg_day': 0.742,
          'gmd_total_kg_day': 0.513,
        });
        return;
      }
      if (request.method == 'GET' && path == '/lotes') {
        await _json(request, 200, [
          {
            'id': 'P01',
            'nome': 'Piquete Central',
            'capacidade_ua': 30.0,
            'animais_ativos': _countAnimals('P01'),
          },
          {
            'id': 'P02',
            'nome': 'Piquete Norte',
            'capacidade_ua': 24.5,
            'animais_ativos': _countAnimals('P02'),
          },
          {
            'id': 'P03',
            'nome': 'Piquete da Baixada',
            'capacidade_ua': null,
            'animais_ativos': _countAnimals('P03'),
          },
        ]);
        return;
      }
      if (request.method == 'POST' && path == '/animais/movimentar') {
        movementRequests++;
        final body = await _body(request);
        lastMovementBody = body;
        final destination = body['to_lote_id'] as String;
        final movidos = <String>[];
        final jaNoDestino = <String>[];
        final erros = <String>[];
        for (final id in List<String>.from(
          body['animal_ids'] as List<dynamic>,
        )) {
          final currentLote = _animalLotes[id];
          if (currentLote == null) {
            erros.add('$id: animal não encontrado');
          } else if (currentLote == destination) {
            jaNoDestino.add(id);
          } else {
            _animalLotes[id] = destination;
            movidos.add(id);
          }
        }
        await _json(request, 200, {
          'movidos': movidos,
          'ja_no_destino': jaNoDestino,
          'erros': erros,
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

  int _countAnimals(String loteId) =>
      _animalLotes.values.where((value) => value == loteId).length;

  List<int>? _multipartFile(List<int> raw, String boundary) {
    final body = latin1.decode(raw);
    const marker = 'name="arquivo"';
    final markerIndex = body.indexOf(marker);
    if (markerIndex < 0) return null;
    final dataStart = body.indexOf('\r\n\r\n', markerIndex);
    if (dataStart < 0) return null;
    final dataEnd = body.indexOf('\r\n--$boundary', dataStart + 4);
    if (dataEnd < 0) return null;
    return latin1.encode(body.substring(dataStart + 4, dataEnd));
  }

  Map<String, dynamic> _animal(String id) => {
    'id': id,
    'breed': 'Nelore',
    'sex': 'M',
    'birth_date': '2024-03-10',
    'entry_weight': 278.2,
    'current_weight': id == 'BR0001' ? currentWeight : 360.0,
    'target_weight': 500.0,
    'status': 'ativo',
    'lote_id': _animalLotes[id],
    'lot_name': switch (_animalLotes[id]) {
      'P01' => 'Piquete Central',
      'P02' => 'Piquete Norte',
      'P03' => 'Piquete da Baixada',
      _ => null,
    },
    'animal_uuid':
        '123e4567-e89b-12d3-a456-42661417400${id.substring(id.length - 1)}',
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
