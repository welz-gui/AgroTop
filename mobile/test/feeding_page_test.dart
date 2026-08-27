import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _TokenStore implements TokenStore {
  _TokenStore()
    : tokens = const StoredTokens(
        accessToken: 'access-live',
        refreshToken: 'refresh-valid',
      );

  StoredTokens? tokens;

  @override
  Future<void> clear() async => tokens = null;

  @override
  Future<StoredTokens?> read() async => tokens;

  @override
  Future<void> write(StoredTokens value) async => tokens = value;
}

http.Response _json(Object body, {int status = 200}) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

List<Map<String, dynamic>> _feedings() => [
  {
    'plano_id': 101,
    'lote_id': 'P01',
    'lote_nome': 'Piquete Central',
    'produto': 'Sal mineral',
    'quantidade': 25.0,
    'unidade': 'kg',
    'frequencia': 'diário',
    'insumo_id': 8,
    'confirmado_no_periodo': false,
    'ultima_confirmacao': null,
  },
  {
    'plano_id': 102,
    'lote_id': 'P01',
    'lote_nome': 'Piquete Central',
    'produto': 'Ração proteica',
    'quantidade': 12.0,
    'unidade': 'kg',
    'frequencia': 'diário',
    'insumo_id': null,
    'confirmado_no_periodo': true,
    'ultima_confirmacao': '2026-08-25',
  },
  {
    'plano_id': 103,
    'lote_id': 'P02',
    'lote_nome': 'Piquete Norte',
    'produto': 'Núcleo mineral',
    'quantidade': 8.0,
    'unidade': 'kg',
    'frequencia': 'semanal',
    'insumo_id': null,
    'confirmado_no_periodo': false,
    'ultima_confirmacao': null,
  },
];

Future<void> _pumpAnimals(WidgetTester tester, ApiClient api) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(colorSchemeSeed: Colors.green),
      home: AnimalsPage(
        api: api,
        themeMode: ThemeMode.light,
        onThemeChanged: (_) {},
        onUnauthorized: () {},
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('abre trato agrupado, confirma item e mantém os demais', (
    tester,
  ) async {
    final feedings = _feedings();
    Map<String, dynamic>? submitted;
    final api = ApiClient(
      tokenStore: _TokenStore(),
      baseUrl: 'http://mock.local',
      httpClient: MockClient((request) async {
        if (request.url.path == '/animais') {
          return _json([
            {
              'id': 'BR0001',
              'breed': 'Nelore',
              'current_weight': 382.4,
              'status': 'ativo',
            },
          ]);
        }
        if (request.method == 'GET' && request.url.path == '/trato/pendentes') {
          return _json(feedings);
        }
        if (request.method == 'POST' &&
            request.url.path == '/trato/101/confirmar') {
          submitted = jsonDecode(request.body) as Map<String, dynamic>;
          return _json({'ok': true}, status: 201);
        }
        return _json({'detail': 'Não encontrado'}, status: 404);
      }),
    );

    await _pumpAnimals(tester, api);
    expect(find.byKey(const ValueKey('pending-feeding-badge')), findsOneWidget);
    expect(find.text('2'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('open-feeding')));
    await tester.pumpAndSettle();
    expect(find.text('2 item(ns) pendente(s)'), findsOneWidget);
    expect(find.byKey(const ValueKey('feeding-lote-P01')), findsOneWidget);
    expect(find.byKey(const ValueKey('feeding-lote-P02')), findsOneWidget);
    expect(find.textContaining('Confirmado em 2026-08-25'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('confirm-feeding-101')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('feeding-deduct-stock')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('feeding-deduct-stock')));
    await tester.enterText(
      find.byKey(const ValueKey('feeding-quantity')),
      '20,5',
    );
    await tester.enterText(
      find.byKey(const ValueKey('feeding-notes')),
      'Restante amanhã',
    );
    await tester.tap(find.byKey(const ValueKey('submit-feeding')));
    await tester.pumpAndSettle();

    expect(submitted, {
      'situacao': 'feito',
      'quantidade_aplicada': 20.5,
      'baixar_estoque': true,
      'notas': 'Restante amanhã',
    });
    expect(find.text('Tudo confirmado'), findsNothing);
    expect(find.text('1 item(ns) pendente(s)'), findsOneWidget);
    expect(find.textContaining('Confirmado agora'), findsOneWidget);
    expect(find.byKey(const ValueKey('feeding-item-103')), findsOneWidget);
  });

  testWidgets('erro conserva formulário e não permite estoque sem insumo', (
    tester,
  ) async {
    final feedings = _feedings();
    var failPost = true;
    final api = ApiClient(
      tokenStore: _TokenStore(),
      baseUrl: 'http://mock.local',
      httpClient: MockClient((request) async {
        if (request.url.path == '/animais') return _json([]);
        if (request.method == 'GET' && request.url.path == '/trato/pendentes') {
          return _json(feedings);
        }
        if (request.method == 'POST' &&
            request.url.path == '/trato/101/confirmar' &&
            failPost) {
          return _json({'detail': 'Sem conexão no mock'}, status: 500);
        }
        return _json({'ok': true}, status: 201);
      }),
    );

    await _pumpAnimals(tester, api);
    await tester.tap(find.byKey(const ValueKey('open-feeding')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('confirm-feeding-101')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey('feeding-quantity')),
      '17',
    );
    await tester.enterText(
      find.byKey(const ValueKey('feeding-notes')),
      'Manter',
    );
    await tester.tap(find.byKey(const ValueKey('submit-feeding')));
    await tester.pumpAndSettle();
    expect(find.text('Sem conexão no mock'), findsOneWidget);
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('feeding-quantity')))
          .controller!
          .text,
      '17',
    );
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('feeding-notes')))
          .controller!
          .text,
      'Manter',
    );

    await tester.tapAt(const Offset(5, 5));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('confirm-feeding-103')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('feeding-deduct-stock')), findsNothing);
    expect(find.byKey(const ValueKey('feeding-no-stock-link')), findsOneWidget);
  });
}
