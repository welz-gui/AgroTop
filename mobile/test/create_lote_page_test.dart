import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/screens/create_lote_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _TokenStore implements TokenStore {
  _TokenStore()
    : _tokens = const StoredTokens(
        accessToken: 'access-live',
        refreshToken: 'refresh-valid',
      );

  StoredTokens? _tokens;

  @override
  Future<void> clear() async => _tokens = null;

  @override
  Future<StoredTokens?> read() async => _tokens;

  @override
  Future<void> write(StoredTokens tokens) async => _tokens = tokens;
}

http.Response _json(Object body, {int status = 200}) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

ApiClient _api(http.Client client) => ApiClient(
  tokenStore: _TokenStore(),
  httpClient: client,
  baseUrl: 'http://mock.local',
);

void main() {
  testWidgets('botão salvar fica desabilitado com campos incompletos ou inválidos', (tester) async {
    final api = _api(MockClient((_) async => _json({})));
    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: CreateLotePage(api: api, onUnauthorized: () {}),
      ),
    );
    await tester.pumpAndSettle();

    final saveButton = find.byKey(const ValueKey('save-lote-button'));
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNull);

    // Preenche apenas ID
    await tester.enterText(find.byKey(const ValueKey('lote-id-field')), 'P99');
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNull);

    // Preenche Nome
    await tester.enterText(find.byKey(const ValueKey('lote-name-field')), 'Piquete Novo');
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNull);

    // Preenche Área negativa
    await tester.enterText(find.byKey(const ValueKey('lote-area-field')), '-5');
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNull);

    // Preenche Área válida e Capacidade negativa
    await tester.enterText(find.byKey(const ValueKey('lote-area-field')), '10.5');
    await tester.enterText(find.byKey(const ValueKey('lote-capacity-field')), '-1');
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNull);

    // Preenche Capacidade válida
    await tester.enterText(find.byKey(const ValueKey('lote-capacity-field')), '20.0');
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(saveButton).onPressed, isNotNull);
  });

  testWidgets('submeter lote válido envia corpo correto, fecha a tela e devolve LoteSummary', (tester) async {
    Map<String, dynamic>? receivedBody;
    LoteSummary? returnedLote;

    final api = _api(
      MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.path, '/lotes');
        receivedBody = jsonDecode(request.body) as Map<String, dynamic>;
        return _json({
          'id': 'P88',
          'nome': 'Piquete 88',
          'capacidade_ua': 22.0,
          'animais_ativos': 0,
        }, status: 201);
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: Builder(
          builder: (context) => Scaffold(
            body: ElevatedButton(
              onPressed: () async {
                returnedLote = await Navigator.of(context).push<LoteSummary>(
                  MaterialPageRoute(
                    builder: (_) => CreateLotePage(api: api, onUnauthorized: () {}),
                  ),
                );
              },
              child: const Text('Abrir'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Abrir'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const ValueKey('lote-id-field')), 'p88');
    await tester.enterText(find.byKey(const ValueKey('lote-name-field')), 'Piquete 88');
    await tester.enterText(find.byKey(const ValueKey('lote-area-field')), '14,5');
    await tester.enterText(find.byKey(const ValueKey('lote-capacity-field')), '22,0');
    await tester.enterText(find.byKey(const ValueKey('lote-notes-field')), 'Pasto rotacionado');
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('save-lote-button')));
    await tester.pumpAndSettle();

    // Tela fechou e voltou para a inicial
    expect(find.byType(CreateLotePage), findsNothing);
    expect(receivedBody, equals({
      'id': 'P88',
      'nome': 'Piquete 88',
      'area_ha': 14.5,
      'capacidade_ua': 22.0,
      'observacoes': 'Pasto rotacionado',
    }));
    expect(returnedLote, isNotNull);
    expect(returnedLote!.id, equals('P88'));
    expect(returnedLote!.nome, equals('Piquete 88'));
    expect(returnedLote!.capacidadeUa, equals(22.0));
    expect(returnedLote!.animaisAtivos, equals(0));
  });

  testWidgets('submeter com ID duplicado (409) exibe erro, não fecha a tela e mantém campos preenchidos', (tester) async {
    final api = _api(
      MockClient((request) async {
        return _json({'detail': 'Lote P01 já existe.'}, status: 409);
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: CreateLotePage(api: api, onUnauthorized: () {}),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const ValueKey('lote-id-field')), 'P01');
    await tester.enterText(find.byKey(const ValueKey('lote-name-field')), 'Piquete Duplicado');
    await tester.enterText(find.byKey(const ValueKey('lote-area-field')), '10.0');
    await tester.enterText(find.byKey(const ValueKey('lote-capacity-field')), '15.0');
    await tester.enterText(find.byKey(const ValueKey('lote-notes-field')), 'Minhas notas');
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('save-lote-button')));
    await tester.pumpAndSettle();

    // Tela NÃO fechou
    expect(find.byType(CreateLotePage), findsOneWidget);
    expect(find.byKey(const ValueKey('lote-error-message')), findsOneWidget);
    expect(find.text('Lote P01 já existe.'), findsOneWidget);

    // Campos continuam preenchidos
    expect(find.text('P01'), findsOneWidget);
    expect(find.text('Piquete Duplicado'), findsOneWidget);
    expect(find.text('10.0'), findsOneWidget);
    expect(find.text('15.0'), findsOneWidget);
    expect(find.text('Minhas notas'), findsOneWidget);
  });

  testWidgets('erro 401 chama onUnauthorized', (tester) async {
    var unauthorizedCalled = false;
    final api = _api(
      MockClient((request) async {
        return _json({'detail': 'Não autenticado'}, status: 401);
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: CreateLotePage(
          api: api,
          onUnauthorized: () => unauthorizedCalled = true,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const ValueKey('lote-id-field')), 'P01');
    await tester.enterText(find.byKey(const ValueKey('lote-name-field')), 'Piquete');
    await tester.enterText(find.byKey(const ValueKey('lote-area-field')), '10.0');
    await tester.enterText(find.byKey(const ValueKey('lote-capacity-field')), '15.0');
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('save-lote-button')));
    await tester.pumpAndSettle();

    expect(unauthorizedCalled, isTrue);
  });
}
