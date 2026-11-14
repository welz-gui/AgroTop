// A fila offline só descarta um item quando o servidor o recusa de forma definitiva (erro de negócio,
// 4xx). Erro passageiro do servidor (5xx, 429, 408) e sessão vencida (401) deixam o item pendente,
// para ser reenviado com a mesma chave: o registro feito no curral não pode sumir porque o banco
// estava pausado ou o token venceu. Antes, qualquer ApiException apagava o item.
import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class _Tokens implements TokenStore {
  StoredTokens? atual = const StoredTokens(accessToken: 'a', refreshToken: 'r');
  @override
  Future<void> clear() async => atual = null;
  @override
  Future<StoredTokens?> read() async => atual;
  @override
  Future<void> write(StoredTokens tokens) async => atual = tokens;
}

http.Response _json(int status, [String corpo = '{"detail":"erro"}']) =>
    http.Response(corpo, status, headers: {'content-type': 'application/json'});

const _pesagemOk =
    '{"status":"success","message":"ok","animal_id":"BR0001","peso":400.0,"data":"2026-11-10"}';

void main() {
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;

  late Database db;
  late OfflineQueue fila;
  late _Tokens tokens;
  late List<http.Request> pedidos;
  // O que o servidor responde a cada pesagem e à renovação da sessão; muda dentro do teste.
  late http.Response Function(http.Request) aPesagem;
  late int statusDoRefresh;

  ApiClient novoApi() => ApiClient(
    tokenStore: tokens,
    baseUrl: 'http://api.local',
    httpClient: MockClient((r) async {
      pedidos.add(r);
      if (r.url.path == '/auth/refresh') {
        return statusDoRefresh == 200
            ? _json(200, '{"access_token":"novo","refresh_token":"r","token_type":"bearer","expires_in":900}')
            : _json(statusDoRefresh);
      }
      return aPesagem(r);
    }),
  );

  Future<void> enfileirar([int quantas = 1]) async {
    for (var i = 0; i < quantas; i++) {
      await fila.enqueueWeighing(animalId: 'BR000${i + 1}', peso: 400.0 + i, data: '2026-11-10');
    }
  }

  setUp(() async {
    db = await databaseFactory.openDatabase(
      inMemoryDatabasePath,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: (db, v) async {
          await db.execute('''
            CREATE TABLE fila_pendente (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              client_uuid TEXT NOT NULL UNIQUE,
              endpoint TEXT NOT NULL,
              metodo TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              criado_em TEXT NOT NULL,
              tentativas INTEGER NOT NULL DEFAULT 0,
              ultimo_erro TEXT
            )
          ''');
        },
      ),
    );
    fila = OfflineQueue(databaseOpener: () async => db);
    tokens = _Tokens();
    pedidos = [];
    aPesagem = (_) => _json(201, _pesagemOk);
    statusDoRefresh = 200;
  });

  // O banco em memória é um só por processo: sem fechar, os itens de um teste vazam para o seguinte.
  tearDown(() async => db.close());

  group('erro passageiro do servidor: o item fica na fila', () {
    for (final status in [500, 502, 503, 504, 429, 408]) {
      test('$status não descarta; reenvia com a mesma chave quando o servidor volta', () async {
        await enfileirar();
        final chave = (await fila.getPendingItems()).single.clientUuid;
        aPesagem = (_) => _json(status);

        final r1 = await fila.sync(novoApi());

        expect(r1.rejeitados, isEmpty, reason: 'o servidor não recusou, tropeçou');
        expect(r1.pendentes.length, 1);
        expect(r1.sincronizados, isEmpty);
        expect(await fila.countPending(), 1, reason: 'o registro continua guardado');
        expect((await fila.getPendingItems()).single.tentativas, 1);

        aPesagem = (_) => _json(201, _pesagemOk);
        final r2 = await fila.sync(novoApi());

        expect(r2.sincronizados.length, 1);
        expect(await fila.countPending(), 0);
        final envios = pedidos.where((p) => p.url.path.endsWith('/pesagens')).toList();
        expect(envios.map((p) => p.headers['Idempotency-Key']).toSet(), {chave},
            reason: 'o reenvio usa a mesma chave de idempotência');
      });
    }

    test('com o servidor fora do ar, não insiste nos demais itens', () async {
      await enfileirar(3);
      aPesagem = (_) => _json(503);

      final r = await fila.sync(novoApi());

      expect(pedidos.where((p) => p.url.path.endsWith('/pesagens')).length, 1,
          reason: 'um 503 já diz que os outros também falhariam; não martela o servidor');
      expect(r.pendentes.length, 3);
      expect(r.rejeitados, isEmpty);
      expect(await fila.countPending(), 3);
    });
  });

  group('sessão vencida: o item fica na fila e o app pede login', () {
    test('401 e a renovação também recusa: nada é descartado', () async {
      await enfileirar(2);
      aPesagem = (_) => _json(401);
      statusDoRefresh = 401;

      final r = await fila.sync(novoApi());

      expect(r.rejeitados, isEmpty);
      expect(r.pendentes.length, 2);
      expect(await fila.countPending(), 2);
      expect(r.pendentes.first.reason, contains('Entre'), reason: 'diz o que fazer');
      expect(tokens.atual, isNull, reason: 'o servidor recusou o token: a sessão acaba mesmo');
    });

    test('depois de entrar de novo, a fila sincroniza', () async {
      await enfileirar(2);
      aPesagem = (_) => _json(401);
      statusDoRefresh = 401;
      await fila.sync(novoApi());

      tokens.atual = const StoredTokens(accessToken: 'login-novo', refreshToken: 'r2');
      aPesagem = (_) => _json(201, _pesagemOk);
      final r = await fila.sync(novoApi());

      expect(r.sincronizados.length, 2);
      expect(await fila.countPending(), 0);
    });

    test('401 e a renovação dá erro do servidor: a sessão NÃO é encerrada e o item fica', () async {
      await enfileirar();
      aPesagem = (_) => _json(401);
      statusDoRefresh = 503;

      final r = await fila.sync(novoApi());

      expect(r.rejeitados, isEmpty);
      expect(await fila.countPending(), 1);
      expect(tokens.atual, isNotNull, reason: 'banco fora do ar não é token inválido');
    });
  });

  group('recusa definitiva continua saindo da fila', () {
    for (final status in [400, 403, 404, 409, 422]) {
      test('$status vai para rejeitados e sai da fila', () async {
        await enfileirar();
        aPesagem = (_) => _json(status, '{"detail":"recusado"}');

        final r = await fila.sync(novoApi());

        expect(r.rejeitados.length, 1);
        expect(r.pendentes, isEmpty);
        expect(await fila.countPending(), 0);
      });
    }

    test('um item recusado não impede os seguintes', () async {
      await enfileirar(2);
      var n = 0;
      aPesagem = (_) => ++n == 1 ? _json(422, '{"detail":"peso inválido"}') : _json(201, _pesagemOk);

      final r = await fila.sync(novoApi());

      expect((r.rejeitados.length, r.sincronizados.length), (1, 1));
      expect(await fila.countPending(), 0);
    });
  });
}
