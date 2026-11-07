import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:flutter_test/flutter_test.dart';

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

class _FakeApi extends ApiClient {
  _FakeApi()
    : super(tokenStore: const _TokenStore(), baseUrl: 'http://localhost:8000');

  final List<Map<String, dynamic>> recebidos = [];
  Object? erro;

  @override
  Future<BruceloseRegistered> registerBruceloseVaccination({
    required List<String> animalIds,
    required String data,
    required String produto,
    required String veterinarioNome,
    String? veterinarioCrmv,
    String? veterinarioUf,
    String? lote,
    String? validade,
    double dose = 2.0,
    String unidade = 'ml',
    String via = 'Subcutânea',
    String? notas,
    String? idempotencyKey,
  }) async {
    if (erro != null) throw erro!;
    recebidos.add({
      'animal_ids': animalIds,
      'data': data,
      'produto': produto,
      'veterinario_nome': veterinarioNome,
      'veterinario_crmv': veterinarioCrmv,
      'veterinario_uf': veterinarioUf,
      'lote': lote,
      'validade': validade,
      'dose': dose,
      'unidade': unidade,
      'via': via,
      'notas': notas,
      'chave': idempotencyKey,
    });
    return BruceloseRegistered(id: 'v1', n: animalIds.length);
  }
}

void main() {
  late OfflineQueue fila;
  late _FakeApi api;

  setUp(() {
    fila = OfflineQueue(storage: MemoryQueueStorage());
    api = _FakeApi();
  });

  Future<String> enfileirar({String? clientUuid}) =>
      fila.enqueueBruceloseVaccination(
        animalIds: ['BR0003', 'BR0005'],
        data: '2027-01-15',
        produto: 'B19',
        veterinarioNome: 'Dra. Ana',
        veterinarioCrmv: '12345',
        veterinarioUf: 'RS',
        lote: 'L-77',
        dose: 1.5,
        clientUuid: clientUuid,
      );

  test('devolve a chave: a que veio ou uma nova', () async {
    expect(await enfileirar(clientUuid: 'minha-chave'), 'minha-chave');
    expect((await enfileirar()).isNotEmpty, isTrue);
  });

  test('só leva ao servidor o que foi informado', () async {
    await enfileirar();

    final payload = (await fila.getPendingItems()).single.payload;

    expect(payload['lote'], 'L-77');
    expect(payload.containsKey('validade'), isFalse);
    expect(payload.containsKey('notas'), isFalse);
    expect(payload['dose'], 1.5);
  });

  test('sync envia o ato com a chave do item e esvazia a fila', () async {
    final chave = await enfileirar();

    final relatorio = await fila.sync(api);

    expect(relatorio.sincronizados, hasLength(1));
    expect(relatorio.isClean, isTrue);
    expect(await fila.countPending(), 0);
    final enviado = api.recebidos.single;
    expect(enviado['chave'], chave);
    expect(enviado['animal_ids'], ['BR0003', 'BR0005']);
    expect(enviado['data'], '2027-01-15');
    expect(enviado['veterinario_nome'], 'Dra. Ana');
    expect(enviado['veterinario_crmv'], '12345');
    expect(enviado['lote'], 'L-77');
    expect(enviado['validade'], isNull);
    expect(enviado['dose'], 1.5);
  });

  test('recusa do servidor descarta o item e diz o motivo', () async {
    await enfileirar();
    api.erro = const ApiException(
      'A vacinação contra brucelose é de fêmeas.',
      statusCode: 422,
    );

    final relatorio = await fila.sync(api);

    expect(relatorio.rejeitados, hasLength(1));
    expect(
      relatorio.rejeitados.single.reason,
      'A vacinação contra brucelose é de fêmeas.',
    );
    expect(await fila.countPending(), 0);
  });

  test('sem conexão o item continua na fila', () async {
    await enfileirar();
    api.erro = Exception('SocketException: Connection refused');

    final relatorio = await fila.sync(api);

    expect(relatorio.pendentes, hasLength(1));
    expect(await fila.countPending(), 1);
  });

  test('chave em processamento no servidor não é recusa', () async {
    await enfileirar();
    api.erro = const ApiException(
      'Requisição com esta Idempotency-Key ainda está em processamento.',
      statusCode: 409,
      emProcessamento: true,
    );

    final relatorio = await fila.sync(api);

    expect(relatorio.rejeitados, isEmpty);
    expect(relatorio.pendentes, hasLength(1));
    expect(await fila.countPending(), 1);
  });
}
