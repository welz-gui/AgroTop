// Registro direto (com sinal) de pesagem, medicamento e movimentação.
//
// Quando o servidor tropeça (5xx, 429, 408), o registro NÃO se perde nem obriga a digitar de novo: vai
// para a fila do aparelho, como já acontecia sem sinal. E, em qualquer dos dois casos, a fila usa a
// MESMA chave de idempotência da tentativa pela rede: se a tentativa tinha chegado ao servidor e só a
// resposta se perdeu, o reenvio devolve o resultado guardado em vez de gravar em dobro.
// Recusa de negócio (422, 409 de conflito) continua aparecendo na tela, e 401 continua pedindo login.
import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/copy.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:agrotop_mobile/screens/medication_page.dart';
import 'package:agrotop_mobile/screens/movement_page.dart';
import 'package:agrotop_mobile/screens/weighing_page.dart';
import 'package:flutter/material.dart';
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

  Object? erro;
  final List<String?> chavesRecebidas = [];

  void _tentar(String? chave) {
    chavesRecebidas.add(chave);
    if (erro != null) throw erro!;
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
    _tentar(idempotencyKey);
    return WeighingResult(
      status: 'success',
      message: 'ok',
      animalId: animalId,
      peso: peso,
      data: data,
    );
  }

  @override
  Future<List<ProtocoloSummary>> listProtocolos({String? animalId}) async =>
      const [];

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
    _tentar(idempotencyKey);
    return '2026-09-15';
  }

  @override
  Future<List<LoteSummary>> listLotes() async => const [
    LoteSummary(id: 'P02', nome: 'Piquete 2', animaisAtivos: 3),
  ];

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
    _tentar(idempotencyKey);
    return MovementResult(movidos: animalIds, jaNoDestino: const [], erros: const []);
  }
}

/// Uma tela de registro: como abri-la, preenchê-la, e o que ela devolve ao voltar com o item na fila.
class _Tela {
  const _Tela(this.nome, this.construir, this.preencher, this.salvar, this.aoEnfileirar, this.endpoint);
  final String nome;
  final Widget Function(_FakeApi api, OfflineQueue fila, VoidCallback aoDeslogar) construir;
  final Future<void> Function(WidgetTester tester) preencher;
  final String salvar; // chave do botão de salvar
  final Object? aoEnfileirar; // o que a tela devolve a quem a abriu
  final String endpoint;
}

Future<void> _digitar(WidgetTester t, String chave, String texto) =>
    t.enterText(find.byKey(ValueKey(chave)), texto);

final _telas = <_Tela>[
  _Tela(
    'pesagem',
    (api, fila, aoDeslogar) => WeighingPage(
      api: api,
      animalId: 'BR0001',
      onUnauthorized: aoDeslogar,
      initialDate: DateTime(2026, 11, 10),
      offlineQueue: fila,
    ),
    (t) => _digitar(t, 'weighing-weight', '412'),
    'save-weighing',
    true,
    '/animais/BR0001/pesagens',
  ),
  _Tela(
    'medicamento',
    (api, fila, aoDeslogar) => MedicationPage(
      api: api,
      animalId: 'BR0001',
      onUnauthorized: aoDeslogar,
      initialDate: DateTime(2026, 11, 10),
      offlineQueue: fila,
    ),
    (t) async {
      await _digitar(t, 'medication-name', 'Ivermectina 1%');
      await _digitar(t, 'medication-dose', '5');
    },
    'save-medication',
    '',
    '/animais/BR0001/medicamentos',
  ),
  _Tela(
    'movimentação',
    (api, fila, aoDeslogar) => MovementPage(
      api: api,
      animalIds: const ['BR0001'],
      onUnauthorized: aoDeslogar,
      initialDate: DateTime(2026, 11, 10),
      offlineQueue: fila,
    ),
    (t) async {
      await t.tap(find.byKey(const ValueKey('movement-lote-P02')));
      await t.pumpAndSettle();
    },
    'confirm-movement',
    true,
    '/animais/movimentar',
  ),
];

void main() {
  late _FakeApi api;
  late OfflineQueue fila;
  late Object? devolvido;
  late bool deslogou;

  Future<void> abrir(WidgetTester tester, _Tela tela) async {
    devolvido = 'não voltou';
    deslogou = false;
    tester.view.physicalSize = const Size(800, 2600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: Center(
              child: ElevatedButton(
                onPressed: () async {
                  devolvido = await Navigator.of(context).push<Object?>(
                    MaterialPageRoute(builder: (_) => tela.construir(api, fila, () => deslogou = true)),
                  );
                },
                child: const Text('abrir'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('abrir'));
    await tester.pumpAndSettle();
  }

  Future<void> salvar(WidgetTester tester, _Tela tela) async {
    await tela.preencher(tester);
    final botao = find.byKey(ValueKey(tela.salvar));
    await tester.ensureVisible(botao);
    await tester.pumpAndSettle();
    await tester.tap(botao);
    await tester.pumpAndSettle();
  }

  setUp(() {
    api = _FakeApi();
    fila = OfflineQueue(storage: MemoryQueueStorage());
  });

  for (final tela in _telas) {
    group('registro direto de ${tela.nome}', () {
      for (final status in [500, 502, 503, 504, 429, 408]) {
        testWidgets('$status do servidor guarda na fila, com a mesma chave da tentativa', (tester) async {
          api.erro = ApiException('erro do servidor', statusCode: status);
          await abrir(tester, tela);

          await salvar(tester, tela);

          expect(devolvido, tela.aoEnfileirar, reason: 'a tela fechou como no registro sem sinal');
          final itens = await fila.getPendingItems();
          expect(itens, hasLength(1), reason: 'o registro não se perde');
          expect(itens.single.endpoint, tela.endpoint);
          expect(api.chavesRecebidas, hasLength(1));
          expect(api.chavesRecebidas.single, isNotNull, reason: 'a tentativa pela rede já leva chave');
          expect(itens.single.clientUuid, api.chavesRecebidas.single,
              reason: 'mesma chave: se a tentativa chegou, o reenvio não grava em dobro');
        });
      }

      testWidgets('resposta perdida (sem sinal) também guarda com a mesma chave da tentativa', (tester) async {
        api.erro = Exception('SocketException: Connection reset');
        await abrir(tester, tela);

        await salvar(tester, tela);

        final itens = await fila.getPendingItems();
        expect(itens, hasLength(1));
        expect(api.chavesRecebidas.single, isNotNull);
        expect(itens.single.clientUuid, api.chavesRecebidas.single,
            reason: 'antes a fila gerava outra chave e a pesagem que tinha chegado era gravada de novo');
      });

      testWidgets('422 aparece na tela e não vai para a fila', (tester) async {
        api.erro = const ApiException('Dado inválido.', statusCode: 422);
        await abrir(tester, tela);

        await salvar(tester, tela);

        expect(find.text('Dado inválido.'), findsOneWidget);
        expect(await fila.countPending(), 0);
        expect(devolvido, 'não voltou');
      });

      testWidgets('409 de conflito de verdade aparece na tela e não vai para a fila', (tester) async {
        api.erro = const ApiException('Animal já está em outro piquete.', statusCode: 409);
        await abrir(tester, tela);

        await salvar(tester, tela);

        expect(find.text('Animal já está em outro piquete.'), findsOneWidget);
        expect(await fila.countPending(), 0);
      });

      testWidgets('401 pede login e não enfileira', (tester) async {
        api.erro = const ApiException('Sessão expirada.', statusCode: 401);
        await abrir(tester, tela);

        await salvar(tester, tela);

        expect(deslogou, isTrue);
        expect(await fila.countPending(), 0);
      });

      testWidgets('sem erro, registra direto e a fila fica vazia', (tester) async {
        await abrir(tester, tela);

        await salvar(tester, tela);

        expect(api.chavesRecebidas, hasLength(1));
        expect(await fila.countPending(), 0);
      });
    });
  }

  test('o aviso de "salvo no aparelho" é o mesmo texto do registro sem sinal', () {
    expect(kOfflineEnfileirado, contains('Salvo neste aparelho'));
  });
}
