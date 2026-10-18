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

  final List<Map<String, dynamic>> chamadas = [];
  ApiException? erro;

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
    if (erro != null) throw erro!;
    chamadas.add({
      'medicamento': medicamento,
      'data': data,
      'principio_ativo': principioAtivo,
      'lote': lote,
      'validade': validade,
    });
    return '2026-09-15';
  }
}

void main() {
  late _FakeApi api;
  String? resultado;

  // A tela faz Navigator.pop ao salvar, então é aberta por cima de outra rota.
  Future<void> abrirTela(WidgetTester tester) async {
    resultado = 'não voltou';
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
                        initialDate: DateTime(2026, 8, 22),
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

  Future<void> preencher(
    WidgetTester tester,
    String chave,
    String texto,
  ) async {
    final finder = find.byKey(ValueKey(chave));
    await tester.ensureVisible(finder);
    await tester.enterText(finder, texto);
  }

  Future<void> salvar(WidgetTester tester) async {
    final botao = find.byKey(const ValueKey('save-medication'));
    await tester.ensureVisible(botao);
    await tester.tap(botao);
    await tester.pumpAndSettle();
  }

  Future<void> preencherObrigatorios(WidgetTester tester) async {
    await preencher(tester, 'medication-name', 'Ivermectina 1%');
    await preencher(tester, 'medication-dose', '5');
  }

  setUp(() => api = _FakeApi());

  testWidgets('salvar envia princípio ativo, lote e validade', (tester) async {
    await abrirTela(tester);
    await preencherObrigatorios(tester);
    await preencher(tester, 'medication-active-ingredient', '  ivermectina ');
    await preencher(tester, 'medication-batch', 'L2410A');
    await preencher(tester, 'medication-expiry', '2027-02-01');

    await salvar(tester);

    expect(api.chamadas, hasLength(1));
    expect(api.chamadas.single['principio_ativo'], 'ivermectina');
    expect(api.chamadas.single['lote'], 'L2410A');
    expect(api.chamadas.single['validade'], '2027-02-01');
    expect(resultado, '2026-09-15');
  });

  testWidgets('sem os campos novos envia nulos e salva normalmente', (
    tester,
  ) async {
    await abrirTela(tester);
    await preencherObrigatorios(tester);

    await salvar(tester);

    expect(api.chamadas, hasLength(1));
    expect(api.chamadas.single['principio_ativo'], isNull);
    expect(api.chamadas.single['lote'], isNull);
    expect(api.chamadas.single['validade'], isNull);
  });

  testWidgets('validade anterior à aplicação bloqueia e não chama a API', (
    tester,
  ) async {
    await abrirTela(tester);
    await preencherObrigatorios(tester);
    await preencher(tester, 'medication-expiry', '2026-08-21');

    await salvar(tester);

    expect(api.chamadas, isEmpty);
    expect(find.textContaining('Produto vencido em 2026-08-21'), findsOneWidget);
    expect(resultado, 'não voltou');
  });

  testWidgets('validade no próprio dia da aplicação ainda vale', (tester) async {
    await abrirTela(tester);
    await preencherObrigatorios(tester);
    await preencher(tester, 'medication-expiry', '2026-08-22');

    await salvar(tester);

    expect(api.chamadas, hasLength(1));
  });

  testWidgets('validade com formato inválido é recusada', (tester) async {
    await abrirTela(tester);
    await preencherObrigatorios(tester);
    await preencher(tester, 'medication-expiry', '31/12/2030');

    await salvar(tester);

    expect(api.chamadas, isEmpty);
    expect(find.text('Use o formato AAAA-MM-DD.'), findsOneWidget);
  });

  testWidgets('lote acima do limite do servidor é recusado', (tester) async {
    await abrirTela(tester);
    await preencherObrigatorios(tester);
    await preencher(tester, 'medication-batch', 'x' * 61);

    await salvar(tester);

    expect(api.chamadas, isEmpty);
    expect(find.text('Máximo de 60 caracteres.'), findsOneWidget);
  });

  testWidgets('422 do servidor aparece na tela e não vira item da fila', (
    tester,
  ) async {
    api.erro = const ApiException(
      'Produto vencido em 2026-08-01: não pode ser aplicado em 2026-08-22.',
      statusCode: 422,
    );
    await abrirTela(tester);
    await preencherObrigatorios(tester);

    await salvar(tester);

    expect(find.textContaining('Produto vencido em 2026-08-01'), findsOneWidget);
    expect(resultado, 'não voltou');
  });
}
