import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
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

  testWidgets('fluxo de telas cobre login, refresh, lista, ficha, pesagem e sanidade', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var currentWeight = 382.4;
    var refreshRequests = 0;
    var weighingRequests = 0;
    var movementRequests = 0;
    var medicationRequests = 0;
    var protocolosRequests = 0;
    String? carenciaAte;
    final aplicacoes = <Map<String, dynamic>>[];
    var currentLote = 'P01';

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
        'lote_id': currentLote,
        'lot_name': currentLote == 'P01' ? 'Piquete Central' : 'Piquete Norte',
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
      if (request.method == 'GET' &&
          request.url.path == '/animais/BR0001/medicamentos') {
        return _json({
          'carencia_ate': carenciaAte,
          'aplicacoes': aplicacoes,
        });
      }
      if (request.method == 'GET' && request.url.path == '/protocolos') {
        protocolosRequests++;
        expect(request.url.queryParameters['animal_id'], 'BR0001');
        return _json([
          {
            'id': 1,
            'nome': 'Ivermectina 1%',
            'via': 'Subcutânea',
            'carencia_dias': 28,
            'unidade_dose': 'ml',
            'dose_sugerida': 7.6,
          },
          {
            'id': 2,
            'nome': 'Vacina Aftosa',
            'via': 'Subcutânea',
            'carencia_dias': 0,
            'unidade_dose': 'ml',
            'dose_sugerida': 2.0,
          },
        ]);
      }
      if (request.method == 'POST' &&
          request.url.path == '/animais/BR0001/medicamentos') {
        medicationRequests++;
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['medicamento'], 'Ivermectina 1%');
        expect(body['dose'], 8.0);
        expect(body['unidade'], 'ml');
        expect(body['via'], 'Subcutânea');
        expect(body['carencia_dias'], 28);
        expect(body['data'], '2026-08-22');
        expect(body['protocolo_id'], 1);
        carenciaAte = '2026-09-19';
        aplicacoes.insert(0, {
          'medicamento': body['medicamento'],
          'dose': body['dose'],
          'unidade': body['unidade'],
          'via': body['via'],
          'carencia_dias': body['carencia_dias'],
          'data': body['data'],
          'protocolo_id': body['protocolo_id'],
        });
        return _json({'carencia_ate': carenciaAte}, status: 201);
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
      if (request.method == 'GET' && request.url.path == '/lotes') {
        return _json([
          {
            'id': 'P01',
            'nome': 'Piquete Central',
            'capacidade_ua': 30.0,
            'animais_ativos': currentLote == 'P01' ? 1 : 0,
          },
          {
            'id': 'P02',
            'nome': 'Piquete Norte',
            'capacidade_ua': 24.5,
            'animais_ativos': currentLote == 'P02' ? 1 : 0,
          },
        ]);
      }
      if (request.method == 'POST' &&
          request.url.path == '/animais/movimentar') {
        movementRequests++;
        expect(jsonDecode(request.body), {
          'animal_ids': ['BR0001'],
          'to_lote_id': 'P02',
          'movement_date': '2026-08-22',
          'reason': 'manejo',
          'notes': null,
        });
        currentLote = 'P02';
        return _json({
          'movidos': ['BR0001'],
          'ja_no_destino': <String>[],
          'erros': <String>[],
        });
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

    // Verifica exibição inicial de carência e histórico vazio
    expect(find.text('Sem restrição de carência'), findsOneWidget);
    expect(find.text('Animal liberado para comercialização/abate.'), findsOneWidget);
    expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);

    final historyCard = find.byKey(const ValueKey('medications-history-card'));
    await tester.scrollUntilVisible(
      historyCard,
      300,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('Nenhuma aplicação registrada.'), findsOneWidget);

    // Fluxo de sanidade: abrir tela de medicamento
    final medicationButton = find.byKey(const ValueKey('open-medication'));
    await tester.scrollUntilVisible(
      medicationButton,
      300,
      scrollable: find.byType(Scrollable).last,
    );
    await tester.tap(medicationButton);
    await tester.pumpAndSettle();
    expect(find.text('Sanidade BR0001'), findsOneWidget);
    expect(protocolosRequests, 1);

    // Selecionar protocolo
    await tester.tap(find.byKey(const ValueKey('protocol-dropdown')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ivermectina 1% (7.6 ml)').last);
    await tester.pumpAndSettle();

    // Conferir campos preenchidos a partir do protocolo (dose_sugerida 7.6)
    expect(find.widgetWithText(TextFormField, 'Ivermectina 1%'), findsOneWidget);
    expect(find.widgetWithText(TextFormField, '7.6'), findsOneWidget);
    expect(find.widgetWithText(TextFormField, 'Subcutânea'), findsOneWidget);
    expect(find.widgetWithText(TextFormField, '28'), findsOneWidget);

    // Editar dose para 8.0 (provando que tudo é editável)
    await tester.enterText(find.byKey(const ValueKey('medication-dose')), '8.0');
    await tester.enterText(find.byKey(const ValueKey('medication-date')), '2026-08-22');
    await tester.tap(find.byKey(const ValueKey('save-medication')));
    await tester.pumpAndSettle();

    expect(medicationRequests, 1);
    expect(find.text('Medicamento registrado com sucesso.'), findsOneWidget);

    // Conferir que a carência agora está ativa com ícone e texto
    expect(find.text('Em carência até 2026-09-19'), findsOneWidget);
    expect(find.text('Abate e comercialização restritos durante este período.'), findsOneWidget);
    expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);

    await tester.scrollUntilVisible(
      historyCard,
      300,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('Histórico de aplicações (1)'), findsOneWidget);
    expect(find.textContaining('Ivermectina 1% · 8.0 ml'), findsOneWidget);

    final weighingButton = find.byKey(const ValueKey('open-weighing'));
    await tester.scrollUntilVisible(
      weighingButton,
      300,
      scrollable: find.byType(Scrollable).last,
    );
    await tester.drag(find.byType(Scrollable).last, const Offset(0, -120));
    await tester.pumpAndSettle();
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

    final movementButton = find.byKey(const ValueKey('open-movement'));
    await tester.scrollUntilVisible(
      movementButton,
      300,
      scrollable: find.byType(Scrollable).last,
    );
    await tester.drag(find.byType(Scrollable).last, const Offset(0, -120));
    await tester.pumpAndSettle();
    await tester.tap(movementButton);
    await tester.pumpAndSettle();
    expect(find.text('Piquete de destino'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('movement-lote-P02')));
    await tester.enterText(
      find.byKey(const ValueKey('movement-date')),
      '2026-08-22',
    );
    await tester.tap(find.byKey(const ValueKey('confirm-movement')));
    await tester.pumpAndSettle();

    expect(movementRequests, 1);
    expect(find.text('Movidos (1)'), findsOneWidget);
    expect(find.text('Já estavam no destino (0)'), findsOneWidget);
    expect(find.text('Erros (0)'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('finish-movement')));
    await tester.pumpAndSettle();
    expect(find.text('Piquete: Piquete Norte'), findsOneWidget);

    Navigator.of(tester.element(find.byType(Scaffold))).pop();
    await tester.pumpAndSettle();
    expect(find.textContaining('P02'), findsOneWidget);
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

  testWidgets('seleção múltipla envia um POST e separa o resultado parcial', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    var movementRequests = 0;
    final sentIds = <String>[];
    final animals = ['BR0001', 'BR0002', 'BR0003']
        .map(
          (id) => {
            'id': id,
            'breed': 'Nelore',
            'sex': 'M',
            'current_weight': 360.0,
            'status': 'ativo',
            'lote_id': id == 'BR0002' ? 'P02' : 'P01',
            'lot_name': id == 'BR0002' ? 'Piquete Norte' : 'Piquete Central',
          },
        )
        .toList(growable: false);
    final api = ApiClient(
      tokenStore: MemoryTokenStore()
        ..tokens = const StoredTokens(
          accessToken: 'access-live',
          refreshToken: 'refresh-valid',
        ),
      baseUrl: 'http://mock.local',
      httpClient: MockClient((request) async {
        if (request.method == 'GET' && request.url.path == '/animais') {
          return _json(animals);
        }
        if (request.method == 'GET' && request.url.path == '/lotes') {
          return _json([
            {
              'id': 'P02',
              'nome': 'Piquete Norte',
              'capacidade_ua': 24.5,
              'animais_ativos': 1,
            },
          ]);
        }
        if (request.method == 'POST' &&
            request.url.path == '/animais/movimentar') {
          movementRequests++;
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          sentIds.addAll(List<String>.from(body['animal_ids'] as List));
          return _json({
            'movidos': ['BR0001'],
            'ja_no_destino': ['BR0002'],
            'erros': ['BR0003: animal bloqueado'],
          });
        }
        return _json({'detail': 'Não encontrado'}, status: 404);
      }),
    );

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
    await tester.tap(find.byKey(const ValueKey('start-animal-selection')));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ListTile, 'BR0001'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ListTile, 'BR0002'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ListTile, 'BR0003'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('move-selected-animals')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const ValueKey('movement-lote-P02')));
    await tester.enterText(
      find.byKey(const ValueKey('movement-date')),
      '2026-08-22',
    );
    await tester.tap(find.byKey(const ValueKey('confirm-movement')));
    await tester.pumpAndSettle();

    expect(movementRequests, 1);
    expect(sentIds, ['BR0001', 'BR0002', 'BR0003']);
    expect(find.text('Movidos (1)'), findsOneWidget);
    expect(find.text('• BR0001'), findsOneWidget);
    expect(find.text('Já estavam no destino (1)'), findsOneWidget);
    expect(find.text('• BR0002'), findsOneWidget);
    expect(find.text('Erros (1)'), findsOneWidget);
    expect(find.text('• BR0003: animal bloqueado'), findsOneWidget);

    final alreadySection = find.byKey(
      const ValueKey('movement-result-already'),
    );
    final errorSection = find.byKey(const ValueKey('movement-result-errors'));
    final context = tester.element(errorSection);
    expect(
      tester
          .widget<Card>(
            find.descendant(of: alreadySection, matching: find.byType(Card)),
          )
          .color,
      Theme.of(context).colorScheme.tertiaryContainer,
    );
    expect(
      tester
          .widget<Card>(
            find.descendant(of: errorSection, matching: find.byType(Card)),
          )
          .color,
      Theme.of(context).colorScheme.errorContainer,
    );
    expect(
      find.descendant(
        of: alreadySection,
        matching: find.byIcon(Icons.info_outline),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: errorSection,
        matching: find.byIcon(Icons.error_outline),
      ),
      findsOneWidget,
    );
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
