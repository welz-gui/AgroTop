// O app diz ao servidor de qual aparelho vem cada escrita (X-Device-Id, PNIB §14.1): um UUID
// aleatório gerado na primeira vez e guardado. O servidor só o aceita no formato
// [A-Za-z0-9._-]{8,64}; um UUID v4 cabe.
import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/device_id.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _MemoriaDoAparelho implements DeviceIdStore {
  String? id;
  int leituras = 0;
  int gravacoes = 0;
  Object? falhaAoLer;
  Object? falhaAoGravar;

  @override
  Future<String?> read() async {
    leituras++;
    if (falhaAoLer != null) throw falhaAoLer!;
    return id;
  }

  @override
  Future<void> write(String novo) async {
    gravacoes++;
    if (falhaAoGravar != null) throw falhaAoGravar!;
    id = novo;
  }
}

class _Tokens implements TokenStore {
  @override
  Future<void> clear() async {}
  @override
  Future<StoredTokens?> read() async =>
      const StoredTokens(accessToken: 'a', refreshToken: 'r');
  @override
  Future<void> write(StoredTokens tokens) async {}
}

final _formatoDoServidor = RegExp(r'^[A-Za-z0-9._-]{8,64}$');

void main() {
  group('obterIdDoAparelho', () {
    test('gera um UUID na primeira vez, guarda e devolve o mesmo depois', () async {
      final store = _MemoriaDoAparelho();

      final primeiro = await obterIdDoAparelho(store);
      final segundo = await obterIdDoAparelho(store);

      expect(primeiro, isNotNull);
      expect(primeiro, matches(_formatoDoServidor));
      expect(segundo, primeiro);
      expect(store.gravacoes, 1, reason: 'só grava na primeira vez');
    });

    test('um aparelho novo (outro armazenamento) tem outro id', () async {
      final a = await obterIdDoAparelho(_MemoriaDoAparelho());
      final b = await obterIdDoAparelho(_MemoriaDoAparelho());
      expect(a, isNot(b));
    });

    test('armazenamento que falha ao ler devolve null, sem derrubar o app', () async {
      final store = _MemoriaDoAparelho()..falhaAoLer = Exception('keystore');
      expect(await obterIdDoAparelho(store), isNull);
    });

    test('falha só ao gravar ainda devolve um id para esta execução', () async {
      final store = _MemoriaDoAparelho()..falhaAoGravar = Exception('cheio');
      final id = await obterIdDoAparelho(store);
      expect(id, matches(_formatoDoServidor));
    });
  });

  group('ApiClient e X-Device-Id', () {
    late List<http.Request> vistos;
    late MockClient cliente;
    var respostas401 = 0;

    setUp(() {
      vistos = [];
      respostas401 = 0;
      cliente = MockClient((request) async {
        vistos.add(request);
        if (request.url.path == '/auth/refresh') {
          return http.Response(
            '{"access_token":"novo","refresh_token":"r2","token_type":"bearer","expires_in":900}',
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        if (respostas401 > 0) {
          respostas401--;
          return http.Response('{"detail":"expirado"}', 401);
        }
        return http.Response(
          '[]',
          200,
          headers: {'content-type': 'application/json'},
        );
      });
    });

    test('toda chamada autenticada leva o mesmo id, lido uma vez', () async {
      final store = _MemoriaDoAparelho();
      final api = ApiClient(
        tokenStore: _Tokens(),
        deviceIdStore: store,
        httpClient: cliente,
        baseUrl: 'http://api.local',
      );

      await api.listLotes();
      await api.listLotes();

      final ids = vistos.map((r) => r.headers['X-Device-Id']).toSet();
      expect(ids.length, 1);
      expect(ids.single, matches(_formatoDoServidor));
      expect(ids.single, store.id);
      expect(store.leituras, 1, reason: 'o id é lido uma vez por execução');
    });

    test('a nova tentativa depois do refresh do token leva o mesmo id', () async {
      respostas401 = 1;
      final api = ApiClient(
        tokenStore: _Tokens(),
        deviceIdStore: _MemoriaDoAparelho(),
        httpClient: cliente,
        baseUrl: 'http://api.local',
      );

      await api.listLotes();

      final lotes = vistos.where((r) => r.url.path != '/auth/refresh').toList();
      expect(lotes.length, 2, reason: 'a 1ª recebeu 401 e a 2ª foi reenviada');
      expect(lotes[0].headers['X-Device-Id'], isNotNull);
      expect(lotes[1].headers['X-Device-Id'], lotes[0].headers['X-Device-Id']);
    });

    test('sem armazenamento do aparelho, a chamada segue sem o cabeçalho', () async {
      final api = ApiClient(
        tokenStore: _Tokens(),
        httpClient: cliente,
        baseUrl: 'http://api.local',
      );

      await api.listLotes();

      expect(vistos.single.headers.containsKey('X-Device-Id'), isFalse);
    });

    test('armazenamento que falha não impede a chamada', () async {
      final api = ApiClient(
        tokenStore: _Tokens(),
        deviceIdStore: _MemoriaDoAparelho()..falhaAoLer = Exception('keystore'),
        httpClient: cliente,
        baseUrl: 'http://api.local',
      );

      await api.listLotes();

      expect(vistos.single.headers.containsKey('X-Device-Id'), isFalse);
    });
  });
}
