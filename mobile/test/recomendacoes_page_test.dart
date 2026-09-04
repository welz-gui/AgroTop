import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/screens/alerts_page.dart';
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

Map<String, dynamic> _emptyAlerts() => {
  'sumidos': [],
  'carencia': [],
  'prontos_para_abate': [],
  'estoque_baixo': [],
  'baixo_desempenho': [],
};

Map<String, dynamic> _alertsWithItems() => {
  'sumidos': [
    {
      'animal_id': 'BR0001',
      'breed': 'Nelore',
      'lote_id': 'P01',
      'peso_atual': 382.4,
      'dias_sem_pesagem': 34,
    },
  ],
  'carencia': [
    {
      'animal_id': 'BR0002',
      'breed': 'Angus',
      'carencia_ate': '2026-09-20',
      'dias_restantes': 15,
    },
  ],
  'prontos_para_abate': [],
  'estoque_baixo': [],
  'baixo_desempenho': [],
};

void main() {

  testWidgets(
    'Critério 2: recomendações fora de ordem são ordenadas por severidade alta -> média -> baixa',
    (tester) async {
      final outOfOrderRecomendacoes = [
        {
          'regra': 'piquete_acima_da_capacidade',
          'severidade': 'baixa',
          'titulo': 'Recomendação Baixa',
          'motivo': 'Motivo da severidade baixa.',
          'dados': {'info': 1},
          'acao': 'Ação baixa',
        },
        {
          'regra': 'estoque_insuficiente',
          'severidade': 'alta',
          'titulo': 'Recomendação Alta',
          'motivo': 'Motivo da severidade alta.',
          'dados': {'info': 2},
          'acao': 'Ação alta urgente',
        },
        {
          'regra': 'gmd_abaixo_da_meta',
          'severidade': 'media',
          'titulo': 'Recomendação Média',
          'motivo': 'Motivo da severidade média.',
          'dados': {'info': 3},
          'acao': 'Ação média',
        },
      ];

      final client = MockClient((request) async {
        if (request.url.path == '/alertas') {
          return _json(_emptyAlerts());
        }
        if (request.url.path == '/recomendacoes') {
          return _json(outOfOrderRecomendacoes);
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
          home: AlertsPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('🧭 Recomendações (3)'), findsOneWidget);

      final posAlta = tester.getTopLeft(find.text('Recomendação Alta')).dy;
      final posMedia = tester.getTopLeft(find.text('Recomendação Média')).dy;
      final posBaixa = tester.getTopLeft(find.text('Recomendação Baixa')).dy;

      expect(posAlta, lessThan(posMedia));
      expect(posMedia, lessThan(posBaixa));

      expect(find.text('👉 Ação alta urgente'), findsOneWidget);
      expect(find.text('👉 Ação média'), findsOneWidget);
      expect(find.text('👉 Ação baixa'), findsOneWidget);
    },
  );

  testWidgets(
    'Critério 3: lista vazia mostra mensagem de sucesso',
    (tester) async {
      final client = MockClient((request) async {
        if (request.url.path == '/alertas') {
          return _json(_emptyAlerts());
        }
        if (request.url.path == '/recomendacoes') {
          return _json([]);
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
          home: AlertsPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('🧭 Recomendações (0)'), findsOneWidget);
      expect(find.text('✅ Nenhuma recomendação no momento.'), findsOneWidget);
    },
  );

  testWidgets(
    'Critério 4: recomendação com acao null não quebra nem mostra "null"',
    (tester) async {
      final recs = [
        {
          'regra': 'regra_sem_acao',
          'severidade': 'alta',
          'titulo': 'Sem Ação Definida',
          'motivo': 'Apenas informativo.',
          'dados': {'info': 99},
          'acao': null,
        },
      ];

      final client = MockClient((request) async {
        if (request.url.path == '/alertas') {
          return _json(_emptyAlerts());
        }
        if (request.url.path == '/recomendacoes') {
          return _json(recs);
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
          home: AlertsPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Sem Ação Definida'), findsOneWidget);
      expect(find.text('Apenas informativo.'), findsOneWidget);
      expect(find.textContaining('null'), findsNothing);
      expect(find.textContaining('👉'), findsNothing);
    },
  );

  testWidgets(
    'Critério 5: pull-to-refresh recarrega alertas e recomendações',
    (tester) async {
      int requestCount = 0;
      final client = MockClient((request) async {
        if (request.url.path == '/alertas') {
          requestCount++;
          return _json(requestCount <= 2 ? _emptyAlerts() : _alertsWithItems());
        }
        if (request.url.path == '/recomendacoes') {
          requestCount++;
          if (requestCount <= 2) {
            return _json([]);
          } else {
            return _json([
              {
                'regra': 'estoque_insuficiente',
                'severidade': 'alta',
                'titulo': 'Estoque urgente após refresh',
                'motivo': 'Insumo acabou.',
                'dados': {},
                'acao': 'Comprar',
              },
            ]);
          }
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
          home: AlertsPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('✅ Nenhuma recomendação no momento.'), findsOneWidget);
      expect(find.text('🔴 Animais Sumidos (0)'), findsOneWidget);

      final refresh = tester
          .state<RefreshIndicatorState>(
            find.byKey(const ValueKey('alerts-refresh')),
          )
          .show();
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      await refresh;
      await tester.pumpAndSettle();

      expect(find.text('Estoque urgente após refresh'), findsOneWidget);
      expect(find.text('🔴 Animais Sumidos (1)'), findsOneWidget);
      expect(find.text('BR0001 — Nelore'), findsOneWidget);
    },
  );

  testWidgets(
    'Critério 6: falha em /recomendacoes não impede os alertas de aparecerem',
    (tester) async {
      final client = MockClient((request) async {
        if (request.url.path == '/alertas') {
          return _json(_alertsWithItems());
        }
        if (request.url.path == '/recomendacoes') {
          return _json({'detail': 'Erro interno do motor'}, status: 500);
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
          home: AlertsPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('🔴 Animais Sumidos (1)'), findsOneWidget);
      expect(find.text('BR0001 — Nelore'), findsOneWidget);
      expect(find.text('🟡 Em Período de Carência (1)'), findsOneWidget);
    },
  );

  testWidgets(
    'Critério 6: falha em /alertas não impede as recomendações de aparecerem',
    (tester) async {
      final client = MockClient((request) async {
        if (request.url.path == '/alertas') {
          return _json({'detail': 'Erro no banco de dados'}, status: 500);
        }
        if (request.url.path == '/recomendacoes') {
          return _json([
            {
              'regra': 'estoque_insuficiente',
              'severidade': 'alta',
              'titulo': 'Recomendação mesmo com alertas caídos',
              'motivo': 'Motivo válido.',
              'dados': {},
              'acao': 'Resolver',
            },
          ]);
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
          home: AlertsPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Recomendação mesmo com alertas caídos'), findsOneWidget);
      expect(find.text('👉 Resolver'), findsOneWidget);
    },
  );

  testWidgets(
    'Erro 401 em /recomendacoes aciona onUnauthorized',
    (tester) async {
      bool unauthorizedCalled = false;

      final client = MockClient((request) async {
        if (request.url.path == '/auth/refresh') {
          return _json({'detail': 'Token inválido'}, status: 401);
        }
        if (request.url.path == '/recomendacoes') {
          return _json({'detail': 'Não autorizado'}, status: 401);
        }
        if (request.url.path == '/alertas') {
          return _json(_emptyAlerts());
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
          home: AlertsPage(
            api: api,
            onUnauthorized: () {
              unauthorizedCalled = true;
            },
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(unauthorizedCalled, isTrue);
    },
  );
}
