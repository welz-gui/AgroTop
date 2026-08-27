import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:agrotop_mobile/shallow_cache.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

class TestTokenStore implements TokenStore {
  StoredTokens? tokens = const StoredTokens(
    accessToken: 'access-live',
    refreshToken: 'refresh-valid',
  );

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

  late OfflineQueue queue;
  late SharedPreferences prefs;
  late ShallowCache shallowCache;

  late bool networkFailWeighing;
  late bool failWeighing422;
  late bool networkFailListAnimals;
  late List<String> receivedIdempotencyKeys;

  setUp(() async {
    networkFailWeighing = false;
    failWeighing422 = false;
    networkFailListAnimals = false;
    receivedIdempotencyKeys = [];

    queue = OfflineQueue(storage: MemoryQueueStorage());
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    shallowCache = ShallowCache(prefs);
  });

  ApiClient createApi() => ApiClient(
    tokenStore: TestTokenStore(),
    baseUrl: 'http://mock.local',
    httpClient: MockClient((request) async {
      if (request.headers['idempotency-key'] != null) {
        receivedIdempotencyKeys.add(request.headers['idempotency-key']!);
      } else if (request.headers['Idempotency-Key'] != null) {
        receivedIdempotencyKeys.add(request.headers['Idempotency-Key']!);
      }

      if (request.method == 'GET' && request.url.path == '/animais') {
        if (networkFailListAnimals) {
          throw http.ClientException('Network error / connection dropped');
        }
        return _json([
          {
            'id': 'BR0001',
            'breed': 'Nelore',
            'sex': 'M',
            'birth_date': '2024-03-10',
            'entry_weight': 278.2,
            'current_weight': 382.4,
            'target_weight': 500.0,
            'status': 'ativo',
            'lote_id': 'P01',
            'lot_name': 'Piquete Central',
            'animal_uuid': '123e4567-e89b-12d3-a456-426614174000',
          },
        ]);
      }
      if (request.method == 'GET' && request.url.path == '/trato/pendentes') {
        return _json([]);
      }
      if (request.method == 'GET' && request.url.path == '/animais/BR0001') {
        return _json({
          'id': 'BR0001',
          'breed': 'Nelore',
          'sex': 'M',
          'birth_date': '2024-03-10',
          'entry_weight': 278.2,
          'current_weight': 382.4,
          'target_weight': 500.0,
          'status': 'ativo',
          'lote_id': 'P01',
          'lot_name': 'Piquete Central',
          'animal_uuid': '123e4567-e89b-12d3-a456-426614174000',
          'entry_date': '2026-01-10',
          'fornecedor_id': 7,
          'fornecedor_name': 'Fazenda Boa Vista',
          'gmd_recent_kg_day': 0.742,
          'gmd_total_kg_day': 0.513,
        });
      }
      if (request.method == 'GET' &&
          request.url.path == '/animais/BR0001/medicamentos') {
        return _json({'carencia_ate': null, 'aplicacoes': []});
      }
      if (request.method == 'GET' &&
          request.url.path == '/animais/BR0001/fotos') {
        return _json([]);
      }
      if (request.method == 'GET' && request.url.path == '/protocolos') {
        return _json([]);
      }
      if (request.method == 'GET' && request.url.path == '/lotes') {
        return _json([
          {
            'id': 'P01',
            'nome': 'Piquete Central',
            'capacidade_ua': 30.0,
            'animais_ativos': 1,
          },
        ]);
      }
      if (request.method == 'POST' &&
          request.url.path == '/animais/BR0001/pesagens') {
        if (networkFailWeighing) {
          throw http.ClientException('Network unreachable');
        }
        if (failWeighing422) {
          return _json({'detail': 'Erro ao registrar pesagem'}, status: 422);
        }
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        return _json({
          'status': 'success',
          'message': 'Pesagem registrada com sucesso.',
          'animal_id': 'BR0001',
          'peso': (body['peso'] as num).toDouble(),
          'data': body['data'],
        }, status: 201);
      }
      return _json({'detail': 'Não encontrado'}, status: 404);
    }),
  );

  testWidgets(
    'Critério 2 & 4: Falha de rede ao registrar pesagem enfileira com sucesso e sincronização posterior envia Idempotency-Key',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final api = createApi();

      await tester.pumpWidget(
        MaterialApp(
          home: AnimalsPage(
            api: api,
            themeMode: ThemeMode.light,
            onThemeChanged: (_) {},
            onUnauthorized: () {},
            offlineQueue: queue,
            shallowCache: shallowCache,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Abrir ficha do animal BR0001
      await tester.tap(find.widgetWithText(ListTile, 'BR0001'));
      await tester.pumpAndSettle();

      // Rolar até o botão de pesagem e abrir tela de pesagem
      await tester.scrollUntilVisible(find.byKey(const ValueKey('open-weighing')), 200);
      await tester.tap(find.byKey(const ValueKey('open-weighing')));
      await tester.pumpAndSettle();

      // Simular queda de rede na pesagem
      networkFailWeighing = true;

      await tester.enterText(find.byKey(const ValueKey('weighing-weight')), '420.5');
      await tester.tap(find.byKey(const ValueKey('save-weighing')));
      await tester.pumpAndSettle();

      // Confirmação de salvo offline e retorno para a ficha sem erro bloqueante
      expect(find.text('Salvo. Será enviado quando houver conexão.'), findsOneWidget);
      expect(await queue.countPending(), equals(1));

      // Voltar para a tela de lista de animais
      Navigator.of(tester.element(find.byKey(const ValueKey('carencia-status-card')))).pop();
      await tester.pumpAndSettle();

      // Badge no botão de sincronização indica 1 pendência
      expect(find.byKey(const ValueKey('pending-queue-badge')), findsOneWidget);
      expect(find.text('1'), findsOneWidget);

      // Normalizar rede e clicar em sincronizar agora
      networkFailWeighing = false;
      await tester.tap(find.byKey(const ValueKey('sync-queue-button')));
      await tester.pumpAndSettle();

      // Diálogo com relatório de sincronização exibindo as 3 seções
      expect(find.text('Relatório de sincronização'), findsOneWidget);
      expect(find.text('Sincronizados com sucesso (1)'), findsOneWidget);
      expect(find.text('Ainda pendentes (0)'), findsOneWidget);
      expect(find.text('Rejeitados pelo servidor (0)'), findsOneWidget);
      expect(find.text('• Pesagem 420.5 kg (BR0001)'), findsOneWidget);

      // Verificar que foi enviado com Idempotency-Key
      expect(receivedIdempotencyKeys.length, equals(1));
      expect(await queue.countPending(), equals(0));

      // Fechar diálogo de relatório
      await tester.tap(find.text('Fechar'));
      await tester.pumpAndSettle();

      // Badge de pendência sumiu
      expect(find.byKey(const ValueKey('pending-queue-badge')), findsNothing);
    },
  );

  testWidgets(
    'Critério 3: Ação que falha por erro real do servidor (422) NÃO é enfileirada e exibe erro imediatamente',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final api = createApi();

      await tester.pumpWidget(
        MaterialApp(
          home: AnimalsPage(
            api: api,
            themeMode: ThemeMode.light,
            onThemeChanged: (_) {},
            onUnauthorized: () {},
            offlineQueue: queue,
            shallowCache: shallowCache,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(ListTile, 'BR0001'));
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(find.byKey(const ValueKey('open-weighing')), 200);
      await tester.tap(find.byKey(const ValueKey('open-weighing')));
      await tester.pumpAndSettle();

      // Simular erro 422 da API
      failWeighing422 = true;

      await tester.enterText(find.byKey(const ValueKey('weighing-weight')), '420.5');
      await tester.tap(find.byKey(const ValueKey('save-weighing')));
      await tester.pumpAndSettle();

      // Erro exibido na própria tela de pesagem, NÃO enfileirado
      expect(find.text('Erro ao registrar pesagem'), findsOneWidget);
      expect(await queue.countPending(), equals(0));
    },
  );

  testWidgets(
    'Critério 5: Item rejeitado durante sincronização sai da fila e aparece em Rejeitados',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      // Enfileirar pesagem previamente
      await queue.enqueueWeighing(
        animalId: 'BR0001',
        peso: 430.0,
        data: '2026-08-27',
      );
      expect(await queue.countPending(), equals(1));

      // Configurar API para rejeitar com 422
      failWeighing422 = true;
      final api = createApi();

      await tester.pumpWidget(
        MaterialApp(
          home: AnimalsPage(
            api: api,
            themeMode: ThemeMode.light,
            onThemeChanged: (_) {},
            onUnauthorized: () {},
            offlineQueue: queue,
            shallowCache: shallowCache,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Clicar no botão de sincronizar
      await tester.tap(find.byKey(const ValueKey('sync-queue-button')));
      await tester.pumpAndSettle();

      // Verificar que foi removido da fila e exibido na seção de rejeitados
      expect(find.text('Relatório de sincronização'), findsOneWidget);
      expect(find.text('Sincronizados com sucesso (0)'), findsOneWidget);
      expect(find.text('Ainda pendentes (0)'), findsOneWidget);
      expect(find.text('Rejeitados pelo servidor (1)'), findsOneWidget);
      expect(find.textContaining('Erro ao registrar pesagem'), findsOneWidget);

      expect(await queue.countPending(), equals(0));
    },
  );

  testWidgets(
    'Critério 6: Cache raso exibe aviso de dados desatualizados quando rede falha',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      // Preencher cache previamente
      await shallowCache.saveAnimals([
        const AnimalSummary(
          id: 'BR0001',
          breed: 'Nelore',
          sex: 'M',
          currentWeight: 382.4,
          loteId: 'P01',
        ),
      ]);

      // Simular falha de rede ao listar animais
      networkFailListAnimals = true;
      final api = createApi();

      await tester.pumpWidget(
        MaterialApp(
          home: AnimalsPage(
            api: api,
            themeMode: ThemeMode.light,
            onThemeChanged: (_) {},
            onUnauthorized: () {},
            offlineQueue: queue,
            shallowCache: shallowCache,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Animal do cache é exibido
      expect(find.text('BR0001'), findsOneWidget);

      // Banner de dados em cache desatualizados é exibido
      expect(find.byKey(const ValueKey('offline-cache-banner')), findsOneWidget);
      expect(find.textContaining('pode estar desatualizado'), findsOneWidget);
      expect(find.byIcon(Icons.cloud_off_outlined), findsOneWidget);
    },
  );
}
