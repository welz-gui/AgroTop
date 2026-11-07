import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:agrotop_mobile/screens/brucelose_pages.dart';
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

  final List<Map<String, dynamic>> registros = [];
  final List<Map<String, dynamic>> acoes = [];
  Object? erroNoRegistro;
  Object? erroNaAcao;
  Object? erroNaLista;
  String? ultimaChave;
  String? prazo = '2027-02-05';
  List<String> avisos = const [];
  List<BruceloseVaccination> lista = const [];
  BruceloseVaccination? detalhe;

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
    ultimaChave = idempotencyKey;
    if (erroNoRegistro != null) throw erroNoRegistro!;
    registros.add({
      'animal_ids': animalIds,
      'data': data,
      'produto': produto,
      'veterinario_nome': veterinarioNome,
      'veterinario_crmv': veterinarioCrmv,
      'veterinario_uf': veterinarioUf,
      'lote': lote,
      'validade': validade,
      'dose': dose,
      'notas': notas,
      'chave': idempotencyKey,
    });
    return BruceloseRegistered(
      id: 'v1',
      n: animalIds.length,
      prazoSda: prazo,
      avisos: avisos,
    );
  }

  @override
  Future<List<BruceloseVaccination>> listBruceloseVaccinations() async {
    if (erroNaLista != null) throw erroNaLista!;
    return lista;
  }

  @override
  Future<BruceloseVaccination> getBruceloseVaccination(String id) async =>
      detalhe!;

  @override
  Future<void> confirmBruceloseSda(
    String id, {
    required String referencia,
    String? idempotencyKey,
  }) async {
    if (erroNaAcao != null) throw erroNaAcao!;
    acoes.add({
      'acao': 'confirmar',
      'id': id,
      'texto': referencia,
      'chave': idempotencyKey,
    });
  }

  @override
  Future<void> bruceloseSdaException(
    String id, {
    required String justificativa,
    String? idempotencyKey,
  }) async {
    if (erroNaAcao != null) throw erroNaAcao!;
    acoes.add({
      'acao': 'excecao',
      'id': id,
      'texto': justificativa,
      'chave': idempotencyKey,
    });
  }

  @override
  Future<void> cancelBruceloseVaccination(
    String id, {
    required String motivo,
    String? idempotencyKey,
  }) async {
    if (erroNaAcao != null) throw erroNaAcao!;
    acoes.add({
      'acao': 'cancelar',
      'id': id,
      'texto': motivo,
      'chave': idempotencyKey,
    });
  }
}

BruceloseVaccination _ato({
  String id = 'v1',
  String status = 'pendente_sda',
  String situacao = 'no_prazo',
  String? prazo = '2027-02-05',
  String? referencia,
  String? justificativa,
  bool cancelada = false,
  List<BruceloseAnimal> animais = const [],
}) => BruceloseVaccination(
  id: id,
  propriedade: 'Fazenda Boa Vista',
  data: '2027-01-15',
  produto: 'B19',
  lote: 'L-77',
  validade: '2028-01-01',
  dose: 2.0,
  unidade: 'ml',
  via: 'Subcutânea',
  veterinarioNome: 'Dra. Ana',
  veterinarioCrmv: '12345',
  veterinarioUf: 'RS',
  nAnimais: 2,
  statusOficial: status,
  referenciaAtestado: referencia,
  justificativaExcecao: justificativa,
  prazoSda: prazo,
  situacaoPrazo: situacao,
  cancelada: cancelada,
  animais: animais,
);

const _animais = [
  BruceloseAnimal(
    brinco: 'BR0003',
    identificadorOficial: '076000000001',
    registroGenealogico: 'RG-9',
  ),
  BruceloseAnimal(brinco: 'BR0005'),
];

void main() {
  late _FakeApi api;
  late OfflineQueue fila;
  Object? resultado;

  setUp(() {
    api = _FakeApi();
    fila = OfflineQueue(storage: MemoryQueueStorage());
  });

  /// Abre [pagina] por cima de uma tela com um botão, para saber o que ela devolve ao fechar.
  Future<void> abrir(WidgetTester tester, Widget Function() pagina) async {
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
                  resultado = await Navigator.of(
                    context,
                  ).push<bool>(MaterialPageRoute(builder: (_) => pagina()));
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

  Future<void> abrirFormulario(WidgetTester tester, {int excluidos = 0}) =>
      abrir(
        tester,
        () => BruceloseVaccinationPage(
          api: api,
          animalIds: const ['BR0003', 'BR0005'],
          excluidos: excluidos,
          onUnauthorized: () {},
          initialDate: DateTime(2027, 1, 15),
          offlineQueue: fila,
        ),
      );

  Future<void> tocar(WidgetTester tester, String chave) async {
    final alvo = find.byKey(ValueKey(chave));
    await tester.ensureVisible(alvo);
    await tester.pumpAndSettle();
    await tester.tap(alvo);
    await tester.pumpAndSettle();
  }

  Future<void> digitar(WidgetTester tester, String chave, String texto) async {
    await tester.enterText(find.byKey(ValueKey(chave)), texto);
  }

  group('rótulos', () {
    test('dataBr troca a ordem e deixa passar o que não é data', () {
      expect(dataBr('2027-02-05'), '05/02/2027');
      expect(dataBr('amanhã'), 'amanhã');
    });

    test('o estado do registro no SDA, em uma linha', () {
      expect(
        rotuloRegistroSda(_ato(situacao: 'atrasado')),
        'Atrasada: o prazo no SDA era 05/02/2027',
      );
      expect(
        rotuloRegistroSda(_ato(situacao: 'vencendo')),
        'Perto do prazo no SDA: até 05/02/2027',
      );
      expect(
        rotuloRegistroSda(_ato()),
        'Pendente no SDA: até 05/02/2027',
      );
      expect(
        rotuloRegistroSda(_ato(prazo: null, situacao: 'sem_prazo')),
        'Pendente no SDA (sem prazo exigido)',
      );
      expect(
        rotuloRegistroSda(
          _ato(status: 'registrado_sda', situacao: 'cumprido', referencia: 'A1'),
        ),
        'Registrada no SDA · atestado A1',
      );
      expect(
        rotuloRegistroSda(_ato(status: 'excecao', situacao: 'cumprido')),
        'Exceção justificada',
      );
      expect(rotuloRegistroSda(_ato(cancelada: true)), 'Cancelada');
    });

    test('só o ato pendente e não cancelado aceita ação', () {
      expect(_ato().pendente, isTrue);
      expect(_ato(status: 'registrado_sda').pendente, isFalse);
      expect(_ato(status: 'excecao').pendente, isFalse);
      expect(_ato(cancelada: true).pendente, isFalse);
    });
  });

  group('formulário', () {
    testWidgets('sem veterinário não envia', (tester) async {
      await abrirFormulario(tester);

      await tocar(tester, 'confirm-brucelose');

      expect(find.text('Informe o médico-veterinário.'), findsOneWidget);
      expect(api.registros, isEmpty);
      expect(resultado, 'não voltou');
    });

    testWidgets('dose zero não envia', (tester) async {
      await abrirFormulario(tester);
      await digitar(tester, 'brucelose-vet', 'Dra. Ana');
      await digitar(tester, 'brucelose-dose', '0');

      await tocar(tester, 'confirm-brucelose');

      expect(find.text('A dose deve ser maior que zero.'), findsOneWidget);
      expect(api.registros, isEmpty);
    });

    testWidgets('validade em formato errado não envia', (tester) async {
      await abrirFormulario(tester);
      await digitar(tester, 'brucelose-vet', 'Dra. Ana');
      await digitar(tester, 'brucelose-validade', '01/2028');

      await tocar(tester, 'confirm-brucelose');

      expect(find.text('Use o formato AAAA-MM-DD.'), findsOneWidget);
      expect(api.registros, isEmpty);
    });

    testWidgets('mostra quantos animais ficaram de fora', (tester) async {
      await abrirFormulario(tester, excluidos: 2);

      expect(
        find.text(
          '2 animais da seleção ficaram de fora: a vacinação é só de fêmeas.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('registra e mostra o prazo no SDA', (tester) async {
      await abrirFormulario(tester);
      await digitar(tester, 'brucelose-vet', '  Dra. Ana ');
      await digitar(tester, 'brucelose-crmv', '12345');
      await digitar(tester, 'brucelose-lote', 'L-77');
      await digitar(tester, 'brucelose-validade', '2028-01-01');

      await tocar(tester, 'confirm-brucelose');

      expect(api.registros, hasLength(1));
      final enviado = api.registros.single;
      expect(enviado['animal_ids'], ['BR0003', 'BR0005']);
      expect(enviado['data'], '2027-01-15');
      expect(enviado['produto'], 'B19');
      expect(enviado['veterinario_nome'], 'Dra. Ana');
      expect(enviado['veterinario_crmv'], '12345');
      expect(enviado['veterinario_uf'], 'RS');
      expect(enviado['lote'], 'L-77');
      expect(enviado['validade'], '2028-01-01');
      expect(enviado['dose'], 2.0);
      expect(enviado['notas'], isNull);
      expect((enviado['chave'] as String).isNotEmpty, isTrue);
      expect(
        tester.widget<Text>(find.byKey(const ValueKey('brucelose-result-title'))).data,
        'Vacinação registrada em 2 animais.',
      );
      expect(find.text('Lançamento no SDA até 05/02/2027.'), findsOneWidget);

      await tocar(tester, 'finish-brucelose');
      expect(resultado, true);
    });

    testWidgets('aceita dose com vírgula', (tester) async {
      await abrirFormulario(tester);
      await digitar(tester, 'brucelose-vet', 'Dra. Ana');
      await digitar(tester, 'brucelose-dose', '1,5');

      await tocar(tester, 'confirm-brucelose');

      expect(api.registros.single['dose'], 1.5);
    });

    testWidgets('antes de 2027 diz que não há prazo no SDA', (tester) async {
      api.prazo = null;
      await abrirFormulario(tester);
      await digitar(tester, 'brucelose-vet', 'Dra. Ana');

      await tocar(tester, 'confirm-brucelose');

      expect(
        find.text(
          'O prazo no SDA só vale para vacinações a partir de 01/01/2027.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('mostra os avisos do servidor', (tester) async {
      api.avisos = ['BR0003: B19 em animal com mais de 8 meses.'];
      await abrirFormulario(tester);
      await digitar(tester, 'brucelose-vet', 'Dra. Ana');

      await tocar(tester, 'confirm-brucelose');

      expect(
        find.text('• BR0003: B19 em animal com mais de 8 meses.'),
        findsOneWidget,
      );
    });

    testWidgets('sem conexão fica na fila com a mesma chave da tentativa', (
      tester,
    ) async {
      api.erroNoRegistro = Exception('SocketException: Connection refused');
      await abrirFormulario(tester);
      await digitar(tester, 'brucelose-vet', 'Dra. Ana');

      await tocar(tester, 'confirm-brucelose');

      expect(resultado, true);
      final itens = await fila.getPendingItems();
      expect(itens, hasLength(1));
      expect(itens.single.clientUuid, api.ultimaChave);
      expect(itens.single.endpoint, '/vacinacoes-brucelose');
      expect(itens.single.payload['animal_ids'], ['BR0003', 'BR0005']);
      expect(itens.single.payload['data'], '2027-01-15');
      expect(
        itens.single.description,
        'Vacinação contra brucelose de 2 animal(is)',
      );
    });

    testWidgets('recusa do servidor aparece na tela e não vai para a fila', (
      tester,
    ) async {
      api.erroNoRegistro = const ApiException(
        'A vacinação contra brucelose é de fêmeas.',
        statusCode: 422,
      );
      await abrirFormulario(tester);
      await digitar(tester, 'brucelose-vet', 'Dra. Ana');

      await tocar(tester, 'confirm-brucelose');

      expect(
        find.text('A vacinação contra brucelose é de fêmeas.'),
        findsOneWidget,
      );
      expect(await fila.countPending(), 0);
      expect(resultado, 'não voltou');
    });
  });

  group('lista', () {
    Future<void> abrirLista(WidgetTester tester) async {
      tester.view.physicalSize = const Size(800, 3000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: BrucelosePage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('mostra o estado do registro de cada ato', (tester) async {
      api.lista = [
        _ato(id: 'a', situacao: 'atrasado'),
        _ato(
          id: 'b',
          status: 'registrado_sda',
          situacao: 'cumprido',
          referencia: 'SDA-9',
        ),
        _ato(id: 'c', prazo: null, situacao: 'sem_prazo'),
      ];

      await abrirLista(tester);

      expect(find.textContaining('Atrasada: o prazo no SDA era 05/02/2027'), findsOneWidget);
      expect(find.textContaining('Registrada no SDA · atestado SDA-9'), findsOneWidget);
      expect(find.textContaining('Pendente no SDA (sem prazo exigido)'), findsOneWidget);
      expect(find.textContaining('15/01/2027 · Fazenda Boa Vista'), findsNWidgets(3));
      expect(find.textContaining('2 animais · B19'), findsNWidgets(3));
    });

    testWidgets('sem vacinação, explica como registrar', (tester) async {
      await abrirLista(tester);

      expect(find.byKey(const ValueKey('brucelose-vazia')), findsOneWidget);
    });

    testWidgets('erro da API aparece e dá para tentar de novo', (tester) async {
      api.erroNaLista = const ApiException('Banco indisponível.', statusCode: 503);
      await abrirLista(tester);

      expect(find.text('Banco indisponível.'), findsOneWidget);

      api.erroNaLista = null;
      api.lista = [_ato()];
      await tester.tap(find.byKey(const ValueKey('brucelose-retry')));
      await tester.pumpAndSettle();

      expect(find.byKey(const ValueKey('brucelose-v1')), findsOneWidget);
    });

    testWidgets('abre o detalhe do ato', (tester) async {
      api.lista = [_ato()];
      api.detalhe = _ato(animais: _animais);
      await abrirLista(tester);

      await tester.tap(find.byKey(const ValueKey('brucelose-v1')));
      await tester.pumpAndSettle();

      expect(find.text('Vacinação contra brucelose'), findsOneWidget);
      expect(find.byKey(const ValueKey('brucelose-animal-BR0003')), findsOneWidget);
    });
  });

  group('detalhe', () {
    Future<void> abrirDetalhe(WidgetTester tester) => abrir(
      tester,
      () => BruceloseDetailPage(
        api: api,
        vacinacaoId: 'v1',
        onUnauthorized: () {},
      ),
    );

    testWidgets('mostra a ficha dos animais e as ações do ato pendente', (
      tester,
    ) async {
      api.detalhe = _ato(animais: _animais);

      await abrirDetalhe(tester);

      expect(find.text('Animais (2)'), findsOneWidget);
      expect(
        find.text(
          'Identificador oficial: 076000000001 · Registro genealógico: RG-9',
        ),
        findsOneWidget,
      );
      expect(
        find.text('Identificador oficial: — · Registro genealógico: —'),
        findsOneWidget,
      );
      expect(find.byKey(const ValueKey('brucelose-confirm')), findsOneWidget);
      expect(find.byKey(const ValueKey('brucelose-excecao')), findsOneWidget);
      expect(find.byKey(const ValueKey('brucelose-cancel')), findsOneWidget);
    });

    testWidgets('ato já registrado no SDA não oferece ação', (tester) async {
      api.detalhe = _ato(
        status: 'registrado_sda',
        situacao: 'cumprido',
        referencia: 'SDA-9',
        animais: _animais,
      );

      await abrirDetalhe(tester);

      expect(find.text('Registrada no SDA · atestado SDA-9'), findsOneWidget);
      expect(find.byKey(const ValueKey('brucelose-confirm')), findsNothing);
      expect(find.byKey(const ValueKey('brucelose-excecao')), findsNothing);
      expect(find.byKey(const ValueKey('brucelose-cancel')), findsNothing);
    });

    testWidgets('confirmar exige a referência do atestado', (tester) async {
      api.detalhe = _ato(animais: _animais);
      await abrirDetalhe(tester);
      await tocar(tester, 'brucelose-confirm');

      await tocar(tester, 'brucelose-confirmar-referencia');

      expect(find.text('Informe a referência do atestado.'), findsOneWidget);
      expect(api.acoes, isEmpty);

      await digitar(tester, 'brucelose-referencia', '  SDA-2027-0042 ');
      await tocar(tester, 'brucelose-confirmar-referencia');

      expect(api.acoes, hasLength(1));
      expect(api.acoes.single['acao'], 'confirmar');
      expect(api.acoes.single['id'], 'v1');
      expect(api.acoes.single['texto'], 'SDA-2027-0042');
      expect((api.acoes.single['chave'] as String).isNotEmpty, isTrue);
      expect(resultado, true);
    });

    testWidgets('exceção exige a justificativa', (tester) async {
      api.detalhe = _ato(animais: _animais);
      await abrirDetalhe(tester);
      await tocar(tester, 'brucelose-excecao');

      await tocar(tester, 'brucelose-confirmar-excecao');
      expect(find.text('Informe a justificativa.'), findsOneWidget);
      expect(api.acoes, isEmpty);

      await digitar(tester, 'brucelose-justificativa', 'Vacinação anterior à exigência');
      await tocar(tester, 'brucelose-confirmar-excecao');

      expect(api.acoes.single['acao'], 'excecao');
      expect(api.acoes.single['texto'], 'Vacinação anterior à exigência');
      expect(resultado, true);
    });

    testWidgets('cancelar exige o motivo', (tester) async {
      api.detalhe = _ato(animais: _animais);
      await abrirDetalhe(tester);
      await tocar(tester, 'brucelose-cancel');

      await tocar(tester, 'brucelose-confirmar-cancelamento');
      expect(find.text('Informe o motivo.'), findsOneWidget);
      expect(api.acoes, isEmpty);

      await digitar(tester, 'brucelose-motivo', 'lançada em duplicidade');
      await tocar(tester, 'brucelose-confirmar-cancelamento');

      expect(api.acoes.single['acao'], 'cancelar');
      expect(api.acoes.single['texto'], 'lançada em duplicidade');
      expect(resultado, true);
    });

    testWidgets('recusa do servidor aparece e a tela continua aberta', (
      tester,
    ) async {
      api.detalhe = _ato(animais: _animais);
      api.erroNaAcao = const ApiException(
        'Vacinação já registrada no SDA: o cancelamento precisa ser feito no SDA.',
        statusCode: 409,
      );
      await abrirDetalhe(tester);
      await tocar(tester, 'brucelose-cancel');
      await digitar(tester, 'brucelose-motivo', 'engano');

      await tocar(tester, 'brucelose-confirmar-cancelamento');

      expect(
        find.text(
          'Vacinação já registrada no SDA: o cancelamento precisa ser feito no SDA.',
        ),
        findsOneWidget,
      );
      expect(resultado, 'não voltou');
    });

    testWidgets('sem conexão avisa que a ação precisa de internet', (
      tester,
    ) async {
      api.detalhe = _ato(animais: _animais);
      api.erroNaAcao = Exception('SocketException: Connection refused');
      await abrirDetalhe(tester);
      await tocar(tester, 'brucelose-confirm');
      await digitar(tester, 'brucelose-referencia', 'SDA-1');

      await tocar(tester, 'brucelose-confirmar-referencia');

      expect(
        find.text(
          'Sem conexão: confirmar ou cancelar uma vacinação precisa de internet. '
          'Tente de novo quando houver sinal.',
        ),
        findsOneWidget,
      );
      expect(resultado, 'não voltou');
    });
  });
}
