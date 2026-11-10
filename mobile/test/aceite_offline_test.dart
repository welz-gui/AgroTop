// Aceite offline, lado do app (plano de 9 de novembro, seção 15.2): dez eventos registrados
// sem sinal chegam ao servidor uma única vez, mesmo quando a resposta de um deles se perde.
//
// O servidor aqui é um fake que imita o contrato da API: executa uma vez por Idempotency-Key e
// responde a repetição com a resposta guardada. Que a API REAL faz isso é provado em
// tests/test_aceite_offline.py; aqui se prova o que é do app: a fila sobrevive a fechar e
// abrir o app, guarda a data de ocorrência, reenvia o item perdido com a MESMA chave, não
// recria o que já foi confirmado e esvazia no fim.
//
// Não coberto: o dispositivo de origem (nenhum cliente o envia hoje).
import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

/// Servidor que executa cada Idempotency-Key uma vez e repete a resposta nas seguintes.
class _ServidorIdempotente extends ApiClient {
  _ServidorIdempotente({this.perderRespostaDaRequisicao})
    : super(tokenStore: const _TokenStore(), baseUrl: 'http://localhost:8000');

  /// Número (1-based) da requisição cuja resposta se perde DEPOIS de o servidor gravar.
  final int? perderRespostaDaRequisicao;
  bool _jaPerdeu = false;

  int requisicoes = 0;
  final List<Map<String, dynamic>> execucoes = [];
  final List<String> repeticoes = [];
  final Set<String> _vistas = {};

  Future<void> _processar(String? chave, Map<String, dynamic> evento) async {
    requisicoes++;
    expect(chave, isNotNull, reason: 'toda escrita da fila leva Idempotency-Key');
    if (_vistas.add(chave!)) {
      execucoes.add({'chave': chave, ...evento});
    } else {
      repeticoes.add(chave);
    }
    if (!_jaPerdeu && requisicoes == perderRespostaDaRequisicao) {
      _jaPerdeu = true;
      throw Exception('SocketException: Connection reset by peer');
    }
  }

  @override
  Future<WeighingResult> registerWeighing(
    String animalId, {
    required double peso,
    required String data,
    String method = 'pesado',
    String notes = '',
    String? idempotencyKey,
  }) async {
    await _processar(idempotencyKey, {
      'tipo': 'pesagem',
      'animal': animalId,
      'data': data,
    });
    return WeighingResult(
      status: 'success',
      message: 'ok',
      animalId: animalId,
      peso: peso,
      data: data,
    );
  }

  @override
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
    String? idempotencyKey,
    String? principioAtivo,
    String? lote,
    String? validade,
  }) async {
    await _processar(idempotencyKey, {
      'tipo': 'aplicacao',
      'animal': animalId,
      'data': data,
    });
    return null;
  }

  @override
  Future<MovementResult> moveAnimals({
    required List<String> animalIds,
    required String toLoteId,
    required String movementDate,
    String? reason = 'manejo',
    String? notes,
    String? idempotencyKey,
    String? loteOrigemEsperado,
    Map<String, String>? origensEsperadas,
  }) async {
    await _processar(idempotencyKey, {
      'tipo': 'movimentacao',
      'animal': animalIds.single,
      'data': movementDate,
    });
    return MovementResult(
      movidos: animalIds,
      jaNoDestino: const [],
      erros: const [],
    );
  }
}

class _TokenStore implements TokenStore {
  const _TokenStore();
  @override
  Future<void> clear() async {}
  @override
  Future<StoredTokens?> read() async =>
      const StoredTokens(accessToken: 'a', refreshToken: 'r');
  @override
  Future<void> write(StoredTokens tokens) async {}
}

void main() {
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;

  late Database db;

  setUp(() async {
    db = await databaseFactory.openDatabase(
      inMemoryDatabasePath,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: (db, version) async {
          // Mesmo esquema de SqfliteQueueStorage (offline_queue_test.dart também o repete).
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
  });

  tearDown(() async => db.close());

  test(
    'dez eventos feitos sem sinal chegam uma única vez, mesmo com a resposta de um perdida',
    () async {
      final queue = OfflineQueue(databaseOpener: () async => db);
      // Sem sinal: os dez só entram na fila.
      final chaves = <String>[];
      final esperado = <Map<String, String>>[];
      for (var i = 0; i < 4; i++) {
        final animal = 'BR000${i + 1}';
        final data = '2026-10-${12 + i}';
        chaves.add(await queue.enqueueWeighing(
          animalId: animal,
          peso: 380.0 + i,
          data: data,
        ));
        esperado.add({'tipo': 'pesagem', 'animal': animal, 'data': data});
      }
      for (var i = 0; i < 4; i++) {
        final animal = 'BR000${i + 5}';
        final data = '2026-10-${16 + i}';
        chaves.add(await queue.enqueueMedication(
          animalId: animal,
          medicamento: 'Ivermectina 1%',
          dose: 8.0,
          unidade: 'ml',
          via: 'Subcutânea',
          carenciaDias: 7,
          data: data,
        ));
        esperado.add({'tipo': 'aplicacao', 'animal': animal, 'data': data});
      }
      for (var i = 0; i < 2; i++) {
        final animal = i == 0 ? 'BR0009' : 'BR0010';
        final data = '2026-10-${25 + i}';
        chaves.add(await queue.enqueueMovement(
          animalIds: [animal],
          toLoteId: i == 0 ? 'P04' : 'P02',
          movementDate: data,
          loteOrigemEsperado: 'P03',
        ));
        esperado.add({'tipo': 'movimentacao', 'animal': animal, 'data': data});
      }
      expect(chaves.toSet().length, 10, reason: 'cada evento tem a sua chave');
      expect(await queue.countPending(), 10);

      // O operador fecha e abre o app: a fila continua lá, com a data de ocorrência.
      final reaberta = OfflineQueue(databaseOpener: () async => db);
      expect(await reaberta.countPending(), 10);
      final itens = await reaberta.getPendingItems();
      expect(itens.map((i) => i.clientUuid), orderedEquals(chaves));
      expect(
        itens.map((i) => i.payload['data'] ?? i.payload['movement_date']),
        orderedEquals(esperado.map((e) => e['data'])),
        reason: 'a data guardada é a do curral, não a da sincronização',
      );

      // A conexão volta ruim: a resposta da 4ª requisição se perde depois de o servidor gravar.
      final servidor = _ServidorIdempotente(perderRespostaDaRequisicao: 4);
      final primeira = await reaberta.sync(servidor);
      expect(primeira.sincronizados.length, 3);
      expect(primeira.pendentes.length, 7);
      expect(primeira.rejeitados, isEmpty);
      expect(await reaberta.countPending(), 7);
      expect(servidor.execucoes.length, 4, reason: 'a 4ª foi gravada e o app não soube');
      final restantes = await reaberta.getPendingItems();
      expect(
        restantes.first.clientUuid,
        chaves[3],
        reason: 'o item perdido volta com a mesma chave, não com uma nova',
      );

      // Conexão boa: o perdido é reenviado e o servidor o responde sem gravar de novo.
      final segunda = await reaberta.sync(servidor);
      expect(segunda.sincronizados.length, 7);
      expect(segunda.pendentes, isEmpty);
      expect(segunda.rejeitados, isEmpty);
      expect(await reaberta.countPending(), 0);

      expect(servidor.execucoes.length, 10);
      expect(servidor.execucoes.map((e) => e['chave']), orderedEquals(chaves));
      expect(servidor.repeticoes, [chaves[3]]);
      expect(servidor.requisicoes, 11);
      for (var i = 0; i < 10; i++) {
        expect(servidor.execucoes[i]['tipo'], esperado[i]['tipo']);
        expect(servidor.execucoes[i]['animal'], esperado[i]['animal']);
        expect(
          servidor.execucoes[i]['data'],
          esperado[i]['data'],
          reason: 'evento $i chegou com a data de ocorrência original',
        );
      }

      // Tocar em sincronizar de novo não envia nada.
      final terceira = await reaberta.sync(servidor);
      expect(terceira.sincronizados, isEmpty);
      expect(servidor.requisicoes, 11);
    },
  );
}
