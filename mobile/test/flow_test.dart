import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

class MemoryTokenStore implements TokenStore {
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

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('fluxo de telas cobre login, refresh, lista, ficha e pesagem', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var currentWeight = 382.4;
    var refreshRequests = 0;
    var weighingRequests = 0;
    final client = MockClient((request) async {
      if (request.method == 'POST' && request.url.path == '/auth/login') {
        expect(jsonDecode(request.body), {
          'username': 'admin',
          'password': 'senha-segura',
        });
        return _json({
          'access_token': 'access-expired',
          'token_type': 'bearer',
          'expires_in': 900,
          'refresh_token': 'refresh-valid',
          'user': {
            'id': 1,
            'username': 'admin',
            'name': 'Administrador',
            'role': 'admin',
          },
        });
      }
      if (request.method == 'POST' && request.url.path == '/auth/refresh') {
        refreshRequests++;
        expect(jsonDecode(request.body), {'refresh_token': 'refresh-valid'});
        return _json({
          'access_token': 'access-live',
          'token_type': 'bearer',
          'expires_in': 900,
        });
      }
      if (request.headers['authorization'] != 'Bearer access-live') {
        return _json({'detail': 'Token inválido ou expirado'}, status: 401);
      }
      final animal = {
        'id': 'BR0001',
        'breed': 'Nelore',
        'sex': 'M',
        'birth_date': '2024-03-10',
        'entry_weight': 278.2,
        'current_weight': currentWeight,
        'target_weight': 500.0,
        'status': 'ativo',
        'lote_id': 'P01',
        'lot_name': 'Piquete Central',
        'animal_uuid': '123e4567-e89b-12d3-a456-426614174000',
      };
      if (request.method == 'GET' && request.url.path == '/animais') {
        expect(request.url.queryParameters, {
          'skip': '0',
          'limit': '50',
          'status': 'ativo',
        });
        return _json([animal]);
      }
      if (request.method == 'GET' && request.url.path == '/animais/BR0001') {
        return _json({
          ...animal,
          'entry_date': '2026-01-10',
          'fornecedor_id': 7,
          'fornecedor_name': 'Fazenda Boa Vista',
          'gmd_recent_kg_day': 0.742,
          'gmd_total_kg_day': 0.513,
        });
      }
      if (request.method == 'POST' &&
          request.url.path == '/animais/BR0001/pesagens') {
        weighingRequests++;
        expect(jsonDecode(request.body), {
          'peso': 401.2,
          'data': '2026-08-22',
          'method': 'pesado',
          'notes': '',
        });
        currentWeight = 401.2;
        return _json({
          'status': 'success',
          'message': 'Pesagem registrada com sucesso.',
          'animal_id': 'BR0001',
          'peso': currentWeight,
          'data': '2026-08-22',
        }, status: 201);
      }
      return _json({'detail': 'Não encontrado'}, status: 404);
    });

    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    final api = ApiClient(
      tokenStore: MemoryTokenStore(),
      httpClient: client,
      baseUrl: 'http://mock.local',
    );

    await tester.pumpWidget(
      AgroTopApp(preferences: preferences, apiClient: api),
    );
    await tester.pumpAndSettle();
    expect(find.text('Gestão do rebanho'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField).at(0), 'admin');
    await tester.enterText(find.byType(TextFormField).at(1), 'senha-segura');
    await tester.tap(find.text('Entrar'));
    await tester.pumpAndSettle();
    expect(find.text('BR0001'), findsOneWidget);
    expect(refreshRequests, 1);

    await tester.enterText(
      find.byKey(const ValueKey('animal-search')),
      'BR0001',
    );
    await tester.tap(find.widgetWithText(ListTile, 'BR0001'));
    await tester.pumpAndSettle();
    expect(find.text('382.4 kg'), findsOneWidget);
    expect(find.text('0.742 kg/dia'), findsOneWidget);

    final weighingButton = find.byKey(const ValueKey('open-weighing'));
    await tester.scrollUntilVisible(
      weighingButton,
      300,
      scrollable: find.byType(Scrollable).last,
    );
    await tester.tap(weighingButton);
    await tester.pumpAndSettle();
    expect(find.text('Pesagem BR0001'), findsOneWidget);

    await tester.enterText(
      find.byKey(const ValueKey('weighing-weight')),
      '401,2',
    );
    await tester.enterText(
      find.byKey(const ValueKey('weighing-date')),
      '2026-08-22',
    );
    await tester.tap(find.byKey(const ValueKey('save-weighing')));
    await tester.pumpAndSettle();

    expect(weighingRequests, 1);
    expect(find.text('Pesagem registrada com sucesso.'), findsOneWidget);
    expect(find.text('401.2 kg'), findsOneWidget);
  });

  testWidgets('servidor indisponível produz erro visível', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    final store = MemoryTokenStore()
      ..tokens = const StoredTokens(
        accessToken: 'access-live',
        refreshToken: 'refresh-valid',
      );
    final api = ApiClient(
      tokenStore: store,
      baseUrl: 'http://mock.local',
      httpClient: MockClient((_) => throw http.ClientException('sem conexão')),
    );

    await tester.pumpWidget(
      AgroTopApp(preferences: preferences, apiClient: api),
    );
    await tester.pumpAndSettle();

    expect(
      find.text('API indisponível. Verifique a conexão e tente novamente.'),
      findsOneWidget,
    );
    expect(find.byType(CircularProgressIndicator), findsNothing);
  });

  testWidgets('refresh recusado limpa tokens e volta ao login', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    final store = MemoryTokenStore()
      ..tokens = const StoredTokens(
        accessToken: 'access-expired',
        refreshToken: 'refresh-revoked',
      );
    final api = ApiClient(
      tokenStore: store,
      baseUrl: 'http://mock.local',
      httpClient: MockClient((request) async {
        if (request.url.path == '/auth/refresh') {
          expect(jsonDecode(request.body), {
            'refresh_token': 'refresh-revoked',
          });
          return _json({'detail': 'Refresh token revogado'}, status: 401);
        }
        return _json({'detail': 'Token expirado'}, status: 401);
      }),
    );

    await tester.pumpWidget(
      AgroTopApp(preferences: preferences, apiClient: api),
    );
    await tester.pumpAndSettle();

    expect(find.text('Gestão do rebanho'), findsOneWidget);
    expect(store.tokens, isNull);
  });
}
