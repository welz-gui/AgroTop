// O app não tinha tempo-limite de rede: com sinal ruim, uma chamada podia ficar pendurada para sempre,
// e a tela nunca chegava ao caminho de "guardar na fila". Agora toda chamada tem limite; ao estourar,
// levanta TempoLimiteDeRede (um TimeoutException, que não é ApiException), e as telas e a fila o tratam
// como falta de conexão: o registro fica guardado e é reenviado com a mesma chave.
import 'dart:async';
import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:agrotop_mobile/tempo_limite.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _Tokens implements TokenStore {
  const _Tokens();
  @override
  Future<void> clear() async {}
  @override
  Future<StoredTokens?> read() async =>
      const StoredTokens(accessToken: 'a', refreshToken: 'r');
  @override
  Future<void> write(StoredTokens tokens) async {}
}

const _curto = Duration(milliseconds: 60);

/// Um servidor que só responde depois de [demora] (ou nunca, se for nulo).
http.Client _servidor({Duration? demora, String corpo = '[]', int status = 200}) =>
    MockClient((request) async {
      if (demora == null) return Completer<http.Response>().future;
      await Future<void>.delayed(demora);
      return http.Response(corpo, status, headers: {'content-type': 'application/json'});
    });

void main() {
  group('ClienteComTempoLimite', () {
    test('servidor que nunca responde: levanta TempoLimiteDeRede, não fica pendurado', () async {
      final cliente = ClienteComTempoLimite(_servidor(), limite: _curto);

      await expectLater(
        cliente.get(Uri.parse('http://api.local/x')),
        throwsA(isA<TempoLimiteDeRede>()),
      );
    });

    test('é um TimeoutException e não um ApiException (as telas tratam como falta de conexão)', () async {
      final cliente = ClienteComTempoLimite(_servidor(), limite: _curto);

      Object? erro;
      try {
        await cliente.get(Uri.parse('http://api.local/x'));
      } catch (e) {
        erro = e;
      }

      expect(erro, isA<TimeoutException>());
      expect(erro, isNot(isA<ApiException>()));
      expect(erro.toString(), isNot(contains('Future not completed')),
          reason: 'a mensagem é a nossa, em português');
    });

    test('resposta rápida passa sem alteração (status, cabeçalhos e corpo)', () async {
      final cliente = ClienteComTempoLimite(
        _servidor(demora: const Duration(milliseconds: 5), corpo: '{"ok":true}', status: 201),
        limite: const Duration(seconds: 5),
      );

      final r = await cliente.get(Uri.parse('http://api.local/x'));

      expect(r.statusCode, 201);
      expect(jsonDecode(r.body), {'ok': true});
      expect(r.headers['content-type'], 'application/json');
    });

    test('corpo que trava no meio também estoura', () async {
      final cliente = ClienteComTempoLimite(
        _ClienteQueTravaNoCorpo(),
        limite: _curto,
        limiteDoCorpo: _curto,
      );

      await expectLater(
        cliente.get(Uri.parse('http://api.local/x')),
        throwsA(isA<TempoLimiteDeRede>()),
      );
    });

    test('corpo lento que anda (dentro do prazo do corpo) não estoura', () async {
      final cliente = ClienteComTempoLimite(
        _ClienteComCorpoLento(const Duration(milliseconds: 200)),
        limite: _curto,
        limiteDoCorpo: const Duration(milliseconds: 900),
      );

      final r = await cliente.get(Uri.parse('http://api.local/x'));

      expect(r.body, '[1,2]');
    });

    test('envio de arquivo (multipart) tem limite maior que o das chamadas comuns', () async {
      // O servidor leva 250 ms: estoura o limite comum (60 ms) mas cabe no de envio (800 ms).
      final servidor = _servidor(demora: const Duration(milliseconds: 250));
      final cliente = ClienteComTempoLimite(
        servidor,
        limite: _curto,
        limiteDeEnvio: const Duration(milliseconds: 800),
      );

      final multipart = http.MultipartRequest('POST', Uri.parse('http://api.local/fotos'))
        ..files.add(http.MultipartFile.fromBytes('file', [1, 2, 3], filename: 'a.jpg'));
      final enviado = await cliente.send(multipart);
      expect(enviado.statusCode, 200);

      await expectLater(
        cliente.get(Uri.parse('http://api.local/x')),
        throwsA(isA<TempoLimiteDeRede>()),
        reason: 'a mesma demora numa chamada comum estoura',
      );
    });
  });

  group('ApiClient', () {
    test('chamada sem resposta levanta TempoLimiteDeRede, e não ApiException', () async {
      final api = ApiClient(
        tokenStore: const _Tokens(),
        baseUrl: 'http://api.local',
        httpClient: _servidor(),
        tempoLimite: _curto,
      );

      await expectLater(api.listLotes(), throwsA(isA<TempoLimiteDeRede>()));
    });

    test('o padrão é 20 s (partida a frio do Cloud Run já passou de 12 s)', () {
      expect(kTempoLimiteDeRede, const Duration(seconds: 20));
      expect(kTempoLimiteDeEnvio, const Duration(seconds: 60));
    });
  });

  group('fila offline com servidor que não responde', () {
    test('o item fica pendente (não é rejeitado nem perdido) e é reenviado com a mesma chave', () async {
      final fila = OfflineQueue(storage: MemoryQueueStorage());
      await fila.enqueueWeighing(animalId: 'BR0001', peso: 400.0, data: '2026-11-10');
      final chave = (await fila.getPendingItems()).single.clientUuid;
      final chaves = <String?>[];
      var responde = false;
      final api = ApiClient(
        tokenStore: const _Tokens(),
        baseUrl: 'http://api.local',
        tempoLimite: _curto,
        httpClient: MockClient((request) async {
          chaves.add(request.headers['Idempotency-Key']);
          if (!responde) return Completer<http.Response>().future;
          return http.Response(
            '{"status":"success","message":"ok","animal_id":"BR0001","peso":400.0,"data":"2026-11-10"}',
            201,
            headers: {'content-type': 'application/json'},
          );
        }),
      );

      final r1 = await fila.sync(api);

      expect(r1.rejeitados, isEmpty);
      expect(r1.pendentes.length, 1);
      expect(await fila.countPending(), 1, reason: 'o registro continua guardado');

      responde = true;
      final r2 = await fila.sync(api);

      expect(r2.sincronizados.length, 1);
      expect(await fila.countPending(), 0);
      expect(chaves.toSet(), {chave}, reason: 'as duas tentativas levam a mesma chave');
    });
  });
}

/// Responde com o cabeçalho e um pedaço do corpo, e depois não manda mais nada.
class _ClienteQueTravaNoCorpo extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final corpo = StreamController<List<int>>()..add(utf8.encode('[1,'));
    return http.StreamedResponse(corpo.stream, 200, request: request);
  }
}

/// Responde logo o cabeçalho e entrega o corpo só depois de [demora].
class _ClienteComCorpoLento extends http.BaseClient {
  _ClienteComCorpoLento(this.demora);
  final Duration demora;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final corpo = Stream<List<int>>.fromFuture(
      Future<List<int>>.delayed(demora, () => utf8.encode('[1,2]')),
    );
    return http.StreamedResponse(corpo, 200, request: request);
  }
}
