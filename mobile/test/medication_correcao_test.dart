import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/screens/medication_page.dart';
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

  final List<Map<String, dynamic>> correcoes = [];
  final List<Map<String, dynamic>> cancelamentos = [];
  final List<Map<String, dynamic>> registros = [];
  Object? erro;

  @override
  Future<List<ProtocoloSummary>> listProtocolos({String? animalId}) async =>
      const [];

  @override
  Future<String?> correctMedication(
    String animalId,
    int aplicacaoId, {
    required String medicamento,
    required double dose,
    required String unidade,
    required String via,
    required int carenciaDias,
    required String data,
    required String motivo,
    int? protocoloId,
    String? notas,
    String? idempotencyKey,
    String? principioAtivo,
    String? lote,
    String? validade,
  }) async {
    if (erro != null) throw erro!;
    correcoes.add({
      'animal': animalId,
      'aplicacao': aplicacaoId,
      'medicamento': medicamento,
      'dose': dose,
      'carencia_dias': carenciaDias,
      'motivo': motivo,
      'protocolo_id': protocoloId,
      'chave': idempotencyKey,
      'lote': lote,
    });
    return '2026-09-05';
  }

  @override
  Future<String?> cancelMedication(
    String animalId,
    int aplicacaoId, {
    required String motivo,
    String? idempotencyKey,
  }) async {
    if (erro != null) throw erro!;
    cancelamentos.add({
      'animal': animalId,
      'aplicacao': aplicacaoId,
      'motivo': motivo,
      'chave': idempotencyKey,
    });
    return null;
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
    registros.add({'medicamento': medicamento});
    return null;
  }
}

const _aplicacao = MedicationApplication(
  id: 7,
  medicamento: 'Ivermectina 1%',
  dose: 50.0,
  unidade: 'ml',
  via: 'Subcutânea',
  carenciaDias: 28,
  data: '2026-08-22',
  protocoloId: 3,
  principioAtivo: 'ivermectina',
  lote: 'L1',
  validade: '2027-01-01',
);

void main() {
  late _FakeApi api;
  String? resultado;

  Future<void> abrirTela(WidgetTester tester) async {
    resultado = 'não voltou';
    tester.view.physicalSize = const Size(800, 3000);
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
                  resultado = await Navigator.of(context).push<String?>(
                    MaterialPageRoute(
                      builder: (_) => MedicationPage(
                        api: api,
                        animalId: 'BR0001',
                        onUnauthorized: () {},
                        corrigir: _aplicacao,
                      ),
                    ),
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

  setUp(() => api = _FakeApi());

  testWidgets('abre preenchida com a aplicação e pede o motivo', (tester) async {
    await abrirTela(tester);

    expect(find.text('Corrigir aplicação BR0001'), findsOneWidget);
    expect(find.byKey(const ValueKey('correction-reason')), findsOneWidget);
    expect(find.widgetWithText(TextFormField, 'Ivermectina 1%'), findsOneWidget);
    expect(find.widgetWithText(TextFormField, '50.0'), findsOneWidget);
    expect(find.widgetWithText(TextFormField, 'L1'), findsOneWidget);
    expect(find.byKey(const ValueKey('protocol-dropdown')), findsNothing);
    expect(find.text('Salvar correção'), findsOneWidget);
    expect(find.byKey(const ValueKey('cancel-medication')), findsOneWidget);
  });

  testWidgets('sem motivo não envia a correção', (tester) async {
    await abrirTela(tester);

    await tocar(tester, 'save-medication');

    expect(find.text('Informe o motivo da correção.'), findsOneWidget);
    expect(api.correcoes, isEmpty);
    expect(resultado, 'não voltou');
  });

  testWidgets('com motivo envia a correção com os campos editados', (tester) async {
    await abrirTela(tester);
    await tester.enterText(
      find.byKey(const ValueKey('correction-reason')),
      '  dose com zero a mais ',
    );
    await tester.enterText(find.byKey(const ValueKey('medication-dose')), '5');
    await tester.enterText(
      find.byKey(const ValueKey('medication-withdrawal-days')),
      '14',
    );

    await tocar(tester, 'save-medication');

    expect(api.correcoes, hasLength(1));
    final c = api.correcoes.single;
    expect(c['aplicacao'], 7);
    expect(c['dose'], 5.0);
    expect(c['carencia_dias'], 14);
    expect(c['motivo'], 'dose com zero a mais');
    expect(c['protocolo_id'], 3, reason: 'a correção mantém o protocolo da original');
    expect(c['chave'], isNotEmpty);
    expect(api.registros, isEmpty, reason: 'não registra uma aplicação nova');
    expect(resultado, '2026-09-05');
  });

  testWidgets('cancelar sem motivo mostra aviso e não pergunta nem envia', (tester) async {
    await abrirTela(tester);

    await tocar(tester, 'cancel-medication');

    expect(find.text('Informe o motivo para cancelar a aplicação.'), findsOneWidget);
    expect(find.text('Cancelar esta aplicação?'), findsNothing);
    expect(api.cancelamentos, isEmpty);
  });

  testWidgets('cancelar com motivo confirma e envia', (tester) async {
    await abrirTela(tester);
    await tester.enterText(
      find.byKey(const ValueKey('correction-reason')),
      'animal errado',
    );

    await tocar(tester, 'cancel-medication');
    expect(find.text('Cancelar esta aplicação?'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('confirm-cancel-medication')));
    await tester.pumpAndSettle();

    expect(api.cancelamentos, hasLength(1));
    expect(api.cancelamentos.single['aplicacao'], 7);
    expect(api.cancelamentos.single['motivo'], 'animal errado');
    expect(resultado, '');
  });

  testWidgets('voltar no diálogo não cancela', (tester) async {
    await abrirTela(tester);
    await tester.enterText(
      find.byKey(const ValueKey('correction-reason')),
      'animal errado',
    );

    await tocar(tester, 'cancel-medication');
    await tester.tap(find.text('Voltar'));
    await tester.pumpAndSettle();

    expect(api.cancelamentos, isEmpty);
    expect(resultado, 'não voltou');
  });

  testWidgets('recusa do servidor aparece na tela e a chave muda', (tester) async {
    await abrirTela(tester);
    await tester.enterText(
      find.byKey(const ValueKey('correction-reason')),
      'erro',
    );
    api.erro = const ApiException('A aplicação 7 já foi cancelada.', statusCode: 409);

    await tocar(tester, 'save-medication');

    expect(find.text('A aplicação 7 já foi cancelada.'), findsOneWidget);
    expect(resultado, 'não voltou');
  });

  testWidgets('sem conexão avisa e não enfileira', (tester) async {
    await abrirTela(tester);
    await tester.enterText(
      find.byKey(const ValueKey('correction-reason')),
      'erro',
    );
    api.erro = Exception('SocketException: Connection refused');

    await tocar(tester, 'save-medication');

    expect(find.textContaining('precisa de internet'), findsOneWidget);
    expect(resultado, 'não voltou');
    expect(api.registros, isEmpty);
  });
}
