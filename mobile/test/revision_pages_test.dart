import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/screens/animal_revision_cards.dart';
import 'package:agrotop_mobile/screens/revision_pages.dart';
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

  final List<Map<String, dynamic>> chamadas = [];
  Object? erro;
  List<WeighingRecord> pesagens = const [];
  List<MovementRecord> movimentacoes = const [];

  @override
  Future<List<LoteSummary>> listLotes() async => const [
    LoteSummary(id: 'P01', nome: 'Piquete Central', animaisAtivos: 3),
    LoteSummary(id: 'P02', nome: 'Piquete Norte', animaisAtivos: 1),
    LoteSummary(id: 'P03', nome: 'Piquete da Baixada', animaisAtivos: 0),
  ];

  @override
  Future<List<WeighingRecord>> listAnimalWeighings(
    String animalId, {
    int limite = 10,
  }) async {
    if (erro != null) throw erro!;
    return pesagens;
  }

  @override
  Future<List<MovementRecord>> listAnimalMovements(
    String animalId, {
    int limite = 10,
  }) async {
    if (erro != null) throw erro!;
    return movimentacoes;
  }

  @override
  Future<double?> correctWeighing(
    String animalId,
    int pesagemId, {
    required double peso,
    required String data,
    required String method,
    required String motivo,
    String notes = '',
    String? idempotencyKey,
  }) async {
    if (erro != null) throw erro!;
    chamadas.add({
      'acao': 'corrigir-pesagem',
      'id': pesagemId,
      'peso': peso,
      'data': data,
      'method': method,
      'motivo': motivo,
      'chave': idempotencyKey,
    });
    return peso;
  }

  @override
  Future<double?> cancelWeighing(
    String animalId,
    int pesagemId, {
    required String motivo,
    String? idempotencyKey,
  }) async {
    if (erro != null) throw erro!;
    chamadas.add({
      'acao': 'cancelar-pesagem',
      'id': pesagemId,
      'motivo': motivo,
      'chave': idempotencyKey,
    });
    return 300.0;
  }

  @override
  Future<String?> correctMovement(
    String animalId,
    int movimentacaoId, {
    required String toLoteId,
    required String movementDate,
    required String motivo,
    String reason = 'manejo',
    String notes = '',
    String? idempotencyKey,
  }) async {
    if (erro != null) throw erro!;
    chamadas.add({
      'acao': 'corrigir-movimentacao',
      'id': movimentacaoId,
      'destino': toLoteId,
      'data': movementDate,
      'reason': reason,
      'motivo': motivo,
    });
    return toLoteId;
  }

  @override
  Future<String?> cancelMovement(
    String animalId,
    int movimentacaoId, {
    required String motivo,
    String? idempotencyKey,
  }) async {
    if (erro != null) throw erro!;
    chamadas.add({
      'acao': 'cancelar-movimentacao',
      'id': movimentacaoId,
      'motivo': motivo,
    });
    return 'P01';
  }
}

const _pesagem = WeighingRecord(
  id: 5,
  data: '2026-08-22',
  peso: 350.5,
  method: 'estimado',
  revisavel: true,
);

const _movimentacao = MovementRecord(
  id: 9,
  de: 'P01',
  para: 'P02',
  data: '2026-08-22',
  motivo: 'manejo',
  revisavel: true,
);

void main() {
  late _FakeApi api;
  Object? resultado;

  // A tela faz Navigator.pop ao salvar, então é aberta por cima de outra rota.
  Future<void> abrir(WidgetTester tester, Widget Function() pagina) async {
    resultado = 'não voltou';
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
                  resultado = await Navigator.of(context).push<bool>(
                    MaterialPageRoute(builder: (_) => pagina()),
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

  Future<void> tocar(WidgetTester tester, String chave) async {
    final alvo = find.byKey(ValueKey(chave));
    await tester.ensureVisible(alvo);
    await tester.pumpAndSettle();
    await tester.tap(alvo);
    await tester.pumpAndSettle();
  }

  Future<void> escrever(WidgetTester tester, String chave, String texto) async {
    await tester.enterText(find.byKey(ValueKey(chave)), texto);
  }

  setUp(() => api = _FakeApi());

  group('pesagem', () {
    Future<void> abrirPesagem(WidgetTester tester) => abrir(
      tester,
      () => WeighingRevisionPage(
        api: api,
        animalId: 'BR0001',
        registro: _pesagem,
        onUnauthorized: () {},
      ),
    );

    testWidgets('abre preenchida com a pesagem e pede o motivo', (tester) async {
      await abrirPesagem(tester);

      expect(find.text('Corrigir pesagem BR0001'), findsOneWidget);
      expect(find.widgetWithText(TextFormField, '350.5'), findsOneWidget);
      expect(find.widgetWithText(TextFormField, '2026-08-22'), findsOneWidget);
      expect(find.byKey(const ValueKey('revision-reason')), findsOneWidget);
      expect(find.text('Salvar correção'), findsOneWidget);
      expect(find.text('Cancelar esta pesagem'), findsOneWidget);
    });

    testWidgets('sem motivo não envia', (tester) async {
      await abrirPesagem(tester);

      await tocar(tester, 'save-revision');

      expect(find.text('Informe o motivo da correção.'), findsOneWidget);
      expect(api.chamadas, isEmpty);
      expect(resultado, 'não voltou');
    });

    testWidgets('com motivo envia o peso editado e volta com true', (tester) async {
      await abrirPesagem(tester);
      await escrever(tester, 'revision-reason', '  digitei errado ');
      await escrever(tester, 'revision-weight', '305,5');

      await tocar(tester, 'save-revision');

      expect(api.chamadas, hasLength(1));
      final c = api.chamadas.single;
      expect(c['acao'], 'corrigir-pesagem');
      expect(c['id'], 5);
      expect(c['peso'], 305.5);
      expect(c['data'], '2026-08-22');
      expect(c['method'], 'estimado');
      expect(c['motivo'], 'digitei errado');
      expect(c['chave'], isNotEmpty);
      expect(resultado, true);
    });

    testWidgets('cancelar sem motivo avisa; com motivo confirma e envia', (tester) async {
      await abrirPesagem(tester);

      await tocar(tester, 'cancel-revision');
      expect(find.text('Informe o motivo para cancelar a pesagem.'), findsOneWidget);
      expect(find.text('Cancelar esta pesagem?'), findsNothing);
      expect(api.chamadas, isEmpty);

      await escrever(tester, 'revision-reason', 'animal errado');
      await tocar(tester, 'cancel-revision');
      expect(find.text('Cancelar esta pesagem?'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('confirm-cancel-revision')));
      await tester.pumpAndSettle();

      expect(api.chamadas.single['acao'], 'cancelar-pesagem');
      expect(api.chamadas.single['motivo'], 'animal errado');
      expect(resultado, true);
    });

    testWidgets('voltar no diálogo não cancela', (tester) async {
      await abrirPesagem(tester);
      await escrever(tester, 'revision-reason', 'animal errado');

      await tocar(tester, 'cancel-revision');
      await tester.tap(find.text('Voltar'));
      await tester.pumpAndSettle();

      expect(api.chamadas, isEmpty);
      expect(resultado, 'não voltou');
    });

    testWidgets('recusa do servidor aparece na tela; falta de rede avisa', (tester) async {
      await abrirPesagem(tester);
      await escrever(tester, 'revision-reason', 'erro');

      api.erro = const ApiException('A pesagem 5 já foi cancelada.', statusCode: 409);
      await tocar(tester, 'save-revision');
      expect(find.text('A pesagem 5 já foi cancelada.'), findsOneWidget);

      api.erro = Exception('SocketException: Connection refused');
      await tocar(tester, 'save-revision');
      expect(find.textContaining('precisa de internet'), findsOneWidget);
      expect(resultado, 'não voltou');
    });
  });

  group('movimentação', () {
    Future<void> abrirMovimentacao(WidgetTester tester) => abrir(
      tester,
      () => MovementRevisionPage(
        api: api,
        animalId: 'BR0001',
        registro: _movimentacao,
        onUnauthorized: () {},
      ),
    );

    testWidgets('mostra a registrada e o destino atual selecionado', (tester) async {
      await abrirMovimentacao(tester);

      expect(find.text('Corrigir movimentação BR0001'), findsOneWidget);
      expect(find.textContaining('P01 → P02 em 2026-08-22'), findsOneWidget);
      expect(find.text('P02 — Piquete Norte'), findsOneWidget);
      expect(find.text('Cancelar e devolver a P01'), findsOneWidget);
    });

    testWidgets('o piquete de origem não é opção de destino', (tester) async {
      await abrirMovimentacao(tester);

      await tester.tap(find.byKey(const ValueKey('revision-destination')));
      await tester.pumpAndSettle();

      expect(find.text('P01 — Piquete Central'), findsNothing);
      expect(find.text('P03 — Piquete da Baixada'), findsWidgets);
    });

    testWidgets('corrigir envia o destino escolhido', (tester) async {
      await abrirMovimentacao(tester);
      await escrever(tester, 'revision-reason', 'era o P03');
      await tester.tap(find.byKey(const ValueKey('revision-destination')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('P03 — Piquete da Baixada').last);
      await tester.pumpAndSettle();

      await tocar(tester, 'save-revision');

      final c = api.chamadas.single;
      expect(c['acao'], 'corrigir-movimentacao');
      expect(c['id'], 9);
      expect(c['destino'], 'P03');
      expect(c['reason'], 'manejo');
      expect(c['motivo'], 'era o P03');
      expect(resultado, true);
    });

    testWidgets('sem motivo não envia; cancelar confirma e envia', (tester) async {
      await abrirMovimentacao(tester);

      await tocar(tester, 'save-revision');
      expect(find.text('Informe o motivo da correção.'), findsOneWidget);
      expect(api.chamadas, isEmpty);

      await escrever(tester, 'revision-reason', 'piquete errado');
      await tocar(tester, 'cancel-revision');
      expect(find.text('Cancelar esta movimentação?'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('confirm-cancel-revision')));
      await tester.pumpAndSettle();

      expect(api.chamadas.single['acao'], 'cancelar-movimentacao');
      expect(api.chamadas.single['motivo'], 'piquete errado');
      expect(resultado, true);
    });
  });

  group('cartões da ficha', () {
    Future<void> abrirCartoes(WidgetTester tester) async {
      tester.view.physicalSize = const Size(800, 2600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: AnimalRevisionCards(
                api: api,
                animalId: 'BR0001',
                onUnauthorized: () {},
                onChanged: () => resultado = 'recarregou',
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('só o que o servidor marca como revisável tem o botão', (tester) async {
      api.pesagens = const [
        _pesagem,
        WeighingRecord(
          id: 1,
          data: '2026-01-10',
          peso: 278.2,
          method: 'pesado',
          revisavel: false,
        ),
      ];
      api.movimentacoes = const [
        _movimentacao,
        MovementRecord(
          id: 8,
          de: 'P03',
          para: 'P01',
          data: '2026-08-01',
          revisavel: false,
        ),
      ];

      await abrirCartoes(tester);

      expect(find.byKey(const ValueKey('weighings-history-card')), findsOneWidget);
      expect(find.byKey(const ValueKey('movements-history-card')), findsOneWidget);
      expect(find.byKey(const ValueKey('correct-weighing-5')), findsOneWidget);
      expect(find.byKey(const ValueKey('correct-weighing-1')), findsNothing);
      expect(find.byKey(const ValueKey('correct-movement-9')), findsOneWidget);
      expect(find.byKey(const ValueKey('correct-movement-8')), findsNothing);
    });

    testWidgets('abre a tela de correção, e ao concluir pede a recarga da ficha', (tester) async {
      resultado = 'não recarregou';
      api.pesagens = const [_pesagem];
      await abrirCartoes(tester);

      await tester.tap(find.byKey(const ValueKey('correct-weighing-5')));
      await tester.pumpAndSettle();
      expect(find.text('Corrigir pesagem BR0001'), findsOneWidget);

      await tester.enterText(find.byKey(const ValueKey('revision-reason')), 'erro');
      await tester.ensureVisible(find.byKey(const ValueKey('save-revision')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('save-revision')));
      await tester.pumpAndSettle();

      expect(api.chamadas.single['acao'], 'corrigir-pesagem');
      expect(resultado, 'recarregou');
      expect(find.text('Registro atualizado. O original fica no histórico.'), findsOneWidget);
    });

    testWidgets('sem as listas (servidor antigo ou falha) os cartões não aparecem', (tester) async {
      api.erro = const ApiException('Não encontrado', statusCode: 404);

      await abrirCartoes(tester);

      expect(find.byType(Card), findsNothing);
      expect(find.byKey(const ValueKey('weighings-history-card')), findsNothing);
    });
  });
}
