import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class FakeApiClient extends ApiClient {
  FakeApiClient()
      : super(
          tokenStore: const _FakeTokenStore(),
          baseUrl: 'http://localhost:8000',
        );

  final List<Map<String, dynamic>> weighingsReceived = [];
  final List<Map<String, dynamic>> medicationsReceived = [];
  final List<Map<String, dynamic>> movementsReceived = [];

  bool throwApiExceptionOnWeighing = false;
  bool throwNetworkExceptionOnMedication = false;

  @override
  Future<WeighingResult> registerWeighing(
    String animalId, {
    required double peso,
    required String data,
    String method = 'pesado',
    String notes = '',
    String? idempotencyKey,
  }) async {
    if (throwApiExceptionOnWeighing) {
      throw const ApiException('Animal não encontrado ou vendido', statusCode: 404);
    }
    weighingsReceived.add({
      'animal_id': animalId,
      'peso': peso,
      'data': data,
      'method': method,
      'notes': notes,
      'idempotency_key': idempotencyKey,
    });
    return WeighingResult(
      status: 'success',
      message: 'Pesagem registrada',
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
  }) async {
    if (throwNetworkExceptionOnMedication) {
      throw Exception('SocketException: Connection refused');
    }
    medicationsReceived.add({
      'animal_id': animalId,
      'medicamento': medicamento,
      'dose': dose,
      'unidade': unidade,
      'via': via,
      'carencia_dias': carenciaDias,
      'data': data,
      'protocolo_id': protocoloId,
      'notas': notas,
      'idempotency_key': idempotencyKey,
    });
    return '2026-09-15';
  }

  @override
  Future<MovementResult> moveAnimals({
    required List<String> animalIds,
    required String toLoteId,
    required String movementDate,
    String? reason = 'manejo',
    String? notes,
    String? idempotencyKey,
  }) async {
    movementsReceived.add({
      'animal_ids': animalIds,
      'to_lote_id': toLoteId,
      'movement_date': movementDate,
      'reason': reason,
      'notes': notes,
      'idempotency_key': idempotencyKey,
    });
    return MovementResult(
      movidos: animalIds,
      jaNoDestino: const [],
      erros: const [],
    );
  }
}

class _FakeTokenStore implements TokenStore {
  const _FakeTokenStore();
  @override
  Future<void> clear() async {}
  @override
  Future<StoredTokens?> read() async => const StoredTokens(accessToken: 'a', refreshToken: 'r');
  @override
  Future<void> write(StoredTokens tokens) async {}
}

void main() {
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;

  group('OfflineQueue', () {
    late OfflineQueue queue;
    late Database db;

    setUp(() async {
      db = await databaseFactory.openDatabase(
        inMemoryDatabasePath,
        options: OpenDatabaseOptions(
          version: 1,
          onCreate: (db, version) async {
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
      queue = OfflineQueue(databaseOpener: () async => db);
    });

    tearDown(() async {
      await db.close();
    });

    test('enfileira pesagem, medicamento e movimentação com client_uuid único', () async {
      expect(await queue.countPending(), equals(0));

      final u1 = await queue.enqueueWeighing(
        animalId: 'BR0001',
        peso: 450.0,
        data: '2026-08-27',
      );
      final u2 = await queue.enqueueMedication(
        animalId: 'BR0001',
        medicamento: 'Aftosa',
        dose: 5.0,
        unidade: 'ml',
        via: 'Subcutânea',
        carenciaDias: 14,
        data: '2026-08-27',
      );
      final u3 = await queue.enqueueMovement(
        animalIds: ['BR0001', 'BR0002'],
        toLoteId: 'P02',
        movementDate: '2026-08-27',
      );

      expect(u1, isNotEmpty);
      expect(u2, isNotEmpty);
      expect(u3, isNotEmpty);
      expect(u1, isNot(equals(u2)));
      expect(u2, isNot(equals(u3)));

      expect(await queue.countPending(), equals(3));
      final items = await queue.getPendingItems();
      expect(items.length, equals(3));
      expect(items[0].clientUuid, equals(u1));
      expect(items[0].endpoint, contains('/pesagens'));
      expect(items[1].clientUuid, equals(u2));
      expect(items[1].endpoint, contains('/medicamentos'));
      expect(items[2].clientUuid, equals(u3));
      expect(items[2].endpoint, contains('/movimentar'));
    });

    test('sincronização com sucesso remove itens e envia Idempotency-Key', () async {
      final fakeApi = FakeApiClient();

      final u1 = await queue.enqueueWeighing(
        animalId: 'BR0001',
        peso: 450.0,
        data: '2026-08-27',
      );
      final u2 = await queue.enqueueMovement(
        animalIds: ['BR0001'],
        toLoteId: 'P02',
        movementDate: '2026-08-27',
      );

      final report = await queue.sync(fakeApi);
      expect(report.sincronizados.length, equals(2));
      expect(report.pendentes, isEmpty);
      expect(report.rejeitados, isEmpty);
      expect(await queue.countPending(), equals(0));

      expect(fakeApi.weighingsReceived.length, equals(1));
      expect(fakeApi.weighingsReceived[0]['idempotency_key'], equals(u1));
      expect(fakeApi.movementsReceived.length, equals(1));
      expect(fakeApi.movementsReceived[0]['idempotency_key'], equals(u2));
    });

    test('item rejeitado pelo servidor (ApiException) sai da fila e vai para rejeitados', () async {
      final fakeApi = FakeApiClient();
      fakeApi.throwApiExceptionOnWeighing = true;

      await queue.enqueueWeighing(
        animalId: 'BR9999',
        peso: 450.0,
        data: '2026-08-27',
      );
      await queue.enqueueMovement(
        animalIds: ['BR0001'],
        toLoteId: 'P02',
        movementDate: '2026-08-27',
      );

      final report = await queue.sync(fakeApi);
      expect(report.rejeitados.length, equals(1));
      expect(report.rejeitados[0].reason, contains('Animal não encontrado ou vendido'));
      expect(report.sincronizados.length, equals(1));
      expect(report.pendentes, isEmpty);

      // Não fica preso na fila
      expect(await queue.countPending(), equals(0));
    });

    test('falha de rede interrompe processamento e mantém itens pendentes', () async {
      final fakeApi = FakeApiClient();
      fakeApi.throwNetworkExceptionOnMedication = true;

      await queue.enqueueMedication(
        animalId: 'BR0001',
        medicamento: 'Aftosa',
        dose: 5.0,
        unidade: 'ml',
        via: 'Subcutânea',
        carenciaDias: 14,
        data: '2026-08-27',
      );
      await queue.enqueueMovement(
        animalIds: ['BR0001'],
        toLoteId: 'P02',
        movementDate: '2026-08-27',
      );

      final report = await queue.sync(fakeApi);
      expect(report.sincronizados, isEmpty);
      expect(report.rejeitados, isEmpty);
      expect(report.pendentes.length, equals(2));
      expect(await queue.countPending(), equals(2));

      final items = await queue.getPendingItems();
      expect(items[0].tentativas, equals(1));
      expect(items[0].ultimoErro, contains('SocketException'));
    });
  });
}
