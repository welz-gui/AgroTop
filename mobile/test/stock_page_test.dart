import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:agrotop_mobile/screens/stock_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class TestTokenStore implements TokenStore {
  StoredTokens? tokens = const StoredTokens(
    accessToken: 'valid-access',
    refreshToken: 'valid-refresh',
  );

  @override
  Future<void> clear() async => tokens = null;

  @override
  Future<StoredTokens?> read() async => tokens;

  @override
  Future<void> write(StoredTokens value) async => tokens = value;
}

http.Response _json(dynamic body, {int status = 200}) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

List<Map<String, dynamic>> _mockInventory() => [
  {
    'id': 1,
    'nome': 'Sal Mineral 80',
    'categoria': 'mineral',
    'estoque_atual': 150.0,
    'estoque_minimo': 100.0,
    'unidade': 'kg',
    'custo_unitario': 3.50,
    'valor_total': 525.00,
    'status': 'ok',
  },
  {
    'id': 2,
    'nome': 'Ração Confinamento',
    'categoria': 'racao',
    'estoque_atual': 45.0,
    'estoque_minimo': 50.0,
    'unidade': 'kg',
    'custo_unitario': 2.80,
    'valor_total': 126.00,
    'status': 'baixo',
  },
  {
    'id': 3,
    'nome': 'Ivermectina 1%',
    'categoria': 'medicamento',
    'estoque_atual': 2.0,
    'estoque_minimo': 10.0,
    'unidade': 'frasco',
    'custo_unitario': 45.00,
    'valor_total': 90.00,
    'status': 'critico',
  },
];

List<Map<String, dynamic>> _mockForecast() => [
  {
    'insumo_id': 2,
    'nome': 'Ração Confinamento',
    'dias_restantes': 3.0,
    'data_ruptura': '2026-09-08',
    'comprar_ate': '2026-09-06',
    'urgencia': 'critica',
  },
  {
    'insumo_id': 1,
    'nome': 'Sal Mineral 80',
    'dias_restantes': 12.0,
    'data_ruptura': '2026-09-17',
    'comprar_ate': '2026-09-14',
    'urgencia': 'atencao',
  },
  {
    'insumo_id': 4,
    'nome': 'Milho Moído',
    'dias_restantes': 45.0,
    'data_ruptura': '2026-10-20',
    'comprar_ate': '2026-10-10',
    'urgencia': 'ok',
  },
  {
    'insumo_id': 3,
    'nome': 'Ivermectina 1%',
    'dias_restantes': null,
    'data_ruptura': null,
    'comprar_ate': null,
    'urgencia': 'sem_dados',
  },
];

void main() {
  testWidgets(
    'Critério 2: abrir tela de estoque a partir de AnimalsPage -> mostra abas e dados',
    (tester) async {
      final client = MockClient((request) async {
        if (request.url.path == '/animais') {
          return _json([
            {
              'id': 'BR0001',
              'breed': 'Nelore',
              'sex': 'M',
              'current_weight': 382.4,
              'status': 'ativo',
              'lote_id': 'P01',
              'birth_date': '2024-03-10',
              'animal_uuid': 'uuid-1',
            },
          ]);
        }
        if (request.url.path == '/trato/pendentes') return _json([]);
        if (request.url.path == '/alertas') {
          return _json({
            'sumidos': [],
            'carencia': [],
            'prontos_para_abate': [],
            'estoque_baixo': [],
            'baixo_desempenho': [],
          });
        }
        if (request.url.path == '/estoque') return _json(_mockInventory());
        if (request.url.path == '/estoque/previsao') {
          return _json(_mockForecast());
        }
        return _json({'detail': 'Not found'}, status: 404);
      });

      final api = ApiClient(
        tokenStore: TestTokenStore(),
        httpClient: client,
        baseUrl: 'http://mock.local',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppThemes.light,
          home: AnimalsPage(
            api: api,
            themeMode: ThemeMode.light,
            onThemeChanged: (_) {},
            onUnauthorized: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Botão de estoque no AppBar
      await tester.tap(find.byTooltip('Open navigation menu'));
      await tester.pumpAndSettle();
      final stockButton = find.byKey(const ValueKey('open-stock'));
      expect(stockButton, findsOneWidget);

      // Clica para abrir StockPage
      tester.widget<ListTile>(stockButton).onTap!();
      await tester.pumpAndSettle();

      // Verifica AppBar e Abas
      expect(find.text('Estoque'), findsOneWidget);
      expect(find.byKey(const ValueKey('tab-inventario')), findsOneWidget);
      expect(find.byKey(const ValueKey('tab-previsao')), findsOneWidget);

      // Aba Inventário: exibe os 3 itens com status
      expect(find.text('Sal Mineral 80'), findsOneWidget);
      expect(find.text('🟢 OK'), findsOneWidget);
      expect(find.text('Categoria: Mineral'), findsOneWidget);

      expect(find.text('Ração Confinamento'), findsOneWidget);
      expect(find.text('🟡 Baixo'), findsOneWidget);
      expect(find.text('Categoria: Ração'), findsOneWidget);

      expect(find.text('Ivermectina 1%'), findsOneWidget);
      expect(find.text('🔴 Crítico'), findsOneWidget);
      expect(find.text('Categoria: Medicamento'), findsOneWidget);

      // Troca para a aba Previsão
      await tester.tap(find.byKey(const ValueKey('tab-previsao')));
      await tester.pumpAndSettle();

      // Aba Previsão: dados de previsão e urgência
      expect(find.text('🔴 Crítica'), findsOneWidget);
      expect(find.text('🟡 Atenção'), findsOneWidget);
      expect(find.text('⚪ Sem dados'), findsOneWidget);

      // Critério 3: item com urgência sem_dados mostra a mensagem explicativa
      expect(find.text('Sem plano de trato ativo'), findsOneWidget);
    },
  );

  testWidgets(
    'Critério 3: item com urgencia: "sem_dados" mostra mensagem explicativa sem datas vazias',
    (tester) async {
      final client = MockClient((request) async {
        if (request.url.path == '/estoque') return _json([]);
        if (request.url.path == '/estoque/previsao') {
          return _json([
            {
              'insumo_id': 99,
              'nome': 'Sal Comum',
              'dias_restantes': null,
              'data_ruptura': null,
              'comprar_ate': null,
              'urgencia': 'sem_dados',
            },
          ]);
        }
        return _json({});
      });

      final api = ApiClient(
        tokenStore: TestTokenStore(),
        httpClient: client,
        baseUrl: 'http://mock.local',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppThemes.light,
          home: StockPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      // Troca para aba Previsão
      await tester.tap(find.byKey(const ValueKey('tab-previsao')));
      await tester.pumpAndSettle();

      expect(find.text('Sal Comum'), findsOneWidget);
      expect(find.text('⚪ Sem dados'), findsOneWidget);
      expect(find.text('Sem plano de trato ativo'), findsOneWidget);
      expect(find.textContaining('Dias restantes:'), findsNothing);
      expect(find.textContaining('Data de ruptura:'), findsNothing);
    },
  );

  testWidgets(
    'Filtro de categoria na aba Inventário filtra itens corretamente',
    (tester) async {
      final client = MockClient((request) async {
        if (request.url.path == '/estoque') return _json(_mockInventory());
        if (request.url.path == '/estoque/previsao') return _json([]);
        return _json({});
      });

      final api = ApiClient(
        tokenStore: TestTokenStore(),
        httpClient: client,
        baseUrl: 'http://mock.local',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppThemes.light,
          home: StockPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Sal Mineral 80'), findsOneWidget);
      expect(find.text('Ração Confinamento'), findsOneWidget);
      expect(find.text('Ivermectina 1%'), findsOneWidget);

      // Abre dropdown e seleciona 'Ração'
      await tester.tap(find.byKey(const ValueKey('stock-category-filter')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Ração').last);
      await tester.pumpAndSettle();

      expect(find.text('Ração Confinamento'), findsOneWidget);
      expect(find.text('Sal Mineral 80'), findsNothing);
      expect(find.text('Ivermectina 1%'), findsNothing);

      // Volta para 'Todas as categorias'
      await tester.tap(find.byKey(const ValueKey('stock-category-filter')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Todas as categorias').last);
      await tester.pumpAndSettle();

      expect(find.text('Sal Mineral 80'), findsOneWidget);
      expect(find.text('Ração Confinamento'), findsOneWidget);
      expect(find.text('Ivermectina 1%'), findsOneWidget);
    },
  );

  testWidgets(
    'Critério 4: Pull-to-refresh recarrega as duas abas com novos dados do mock',
    (tester) async {
      int inventoryCalls = 0;
      int forecastCalls = 0;

      final client = MockClient((request) async {
        if (request.url.path == '/estoque') {
          inventoryCalls++;
          if (inventoryCalls == 1) {
            return _json([
              {
                'id': 1,
                'nome': 'Item Inicial',
                'categoria': 'outro',
                'estoque_atual': 10.0,
                'estoque_minimo': 5.0,
                'unidade': 'un',
                'custo_unitario': 10.0,
                'valor_total': 100.0,
                'status': 'ok',
              },
            ]);
          } else {
            return _json([
              {
                'id': 2,
                'nome': 'Item Atualizado',
                'categoria': 'outro',
                'estoque_atual': 2.0,
                'estoque_minimo': 5.0,
                'unidade': 'un',
                'custo_unitario': 10.0,
                'valor_total': 20.0,
                'status': 'baixo',
              },
            ]);
          }
        }
        if (request.url.path == '/estoque/previsao') {
          forecastCalls++;
          if (forecastCalls == 1) {
            return _json([
              {
                'insumo_id': 1,
                'nome': 'Previsão Inicial',
                'dias_restantes': 15.0,
                'data_ruptura': '2026-09-20',
                'comprar_ate': '2026-09-15',
                'urgencia': 'ok',
              },
            ]);
          } else {
            return _json([
              {
                'insumo_id': 2,
                'nome': 'Previsão Atualizada',
                'dias_restantes': 2.0,
                'data_ruptura': '2026-09-07',
                'comprar_ate': '2026-09-05',
                'urgencia': 'critica',
              },
            ]);
          }
        }
        return _json({});
      });

      final api = ApiClient(
        tokenStore: TestTokenStore(),
        httpClient: client,
        baseUrl: 'http://mock.local',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppThemes.light,
          home: StockPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Item Inicial'), findsOneWidget);

      // Pull to refresh na aba Inventário
      await tester.fling(
        find.byKey(const ValueKey('stock-inventory-refresh')),
        const Offset(0, 300),
        1000,
      );
      await tester.pumpAndSettle();

      expect(find.text('Item Atualizado'), findsOneWidget);
      expect(find.text('Item Inicial'), findsNothing);

      // Troca para Previsão e verifica se a segunda chamada já ocorreu e exibiu Previsão Atualizada
      await tester.tap(find.byKey(const ValueKey('tab-previsao')));
      await tester.pumpAndSettle();

      expect(find.text('Previsão Atualizada'), findsOneWidget);

      // Pull to refresh na aba Previsão
      await tester.fling(
        find.byKey(const ValueKey('stock-forecast-refresh')),
        const Offset(0, 300),
        1000,
      );
      await tester.pumpAndSettle();

      expect(forecastCalls, greaterThanOrEqualTo(3));
    },
  );

  testWidgets('401 não autorizado chama callback onUnauthorized', (
    tester,
  ) async {
    bool unauthorizedCalled = false;
    final client = MockClient((request) async {
      return _json({'detail': 'Token expired'}, status: 401);
    });

    final api = ApiClient(
      tokenStore: TestTokenStore(),
      httpClient: client,
      baseUrl: 'http://mock.local',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: StockPage(
          api: api,
          onUnauthorized: () => unauthorizedCalled = true,
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(unauthorizedCalled, isTrue);
  });
}
