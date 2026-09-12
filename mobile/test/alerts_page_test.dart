import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/screens/alerts_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _TestTokenStore implements TokenStore {
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

Map<String, dynamic> _allAlertsPayload() => {
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
  'prontos_para_abate': [
    {
      'animal_id': 'BR0003',
      'breed': 'Nelore',
      'peso_atual': 510.0,
      'peso_alvo': 500.0,
      'arrobas': 17.68,
    },
  ],
  'estoque_baixo': [
    {
      'insumo_id': 1,
      'nome': 'Sal mineral',
      'estoque_atual': 5.0,
      'estoque_minimo': 10.0,
      'unidade': 'kg',
    },
  ],
  'baixo_desempenho': [
    {
      'animal_id': 'BR0004',
      'breed': 'Brahman',
      'lote_id': 'P02',
      'peso_atual': 355.0,
      'gmd': 0.31,
      'meta_gmd': 0.5,
    },
  ],
};

List<Map<String, dynamic>> _recomendacoesPayload() => [
  {
    'regra': 'estoque_insuficiente',
    'severidade': 'alta',
    'titulo': 'Estoque crítico de ração',
    'motivo': 'Ficará sem ração em 2 dias.',
    'acao': 'Repor ração',
    'dados': {'dias': 2},
  },
  {
    'regra': 'gmd_abaixo_da_meta',
    'severidade': 'media',
    'titulo': 'GMD abaixo da meta',
    'motivo': 'GMD 20% abaixo.',
    'acao': 'Ajustar suplementação',
    'dados': {},
  },
  {
    'regra': 'carencia_impede_abate',
    'severidade': 'baixa',
    'titulo': 'Atenção ao calendário',
    'motivo': 'Período de carência em breve.',
    'acao': 'Revisar abates',
    'dados': {},
  },
];

void main() {
  Card findCardAncestor(WidgetTester tester, Finder finder) {
    return tester.widget<Card>(
      find.ancestor(of: finder, matching: find.byType(Card)),
    );
  }

  group('Spec 0087 - Borda colorida dos cards de alerta', () {
    for (final isDark in [false, true]) {
      final themeName = isDark ? 'dark' : 'light';
      final tokens = isDark ? AppColors.dark : AppColors.light;
      final themeData = isDark ? AppThemes.dark : AppThemes.light;

      testWidgets(
        'Critérios 1, 2 e 3: borda correta em sumidos, carencia, estoque e neutra em prontos e baixo desempenho ($themeName)',
        (tester) async {
          final client = MockClient((request) async {
            if (request.url.path == '/alertas') {
              return _json(_allAlertsPayload());
            }
            if (request.url.path == '/recomendacoes') {
              return _json([]);
            }
            return _json({'detail': 'Not found'}, status: 404);
          });

          final api = ApiClient(
            tokenStore: _TestTokenStore(),
            httpClient: client,
            baseUrl: 'http://mock.local',
          );

          await tester.pumpWidget(
            MaterialApp(
              theme: themeData,
              home: AlertsPage(api: api, onUnauthorized: () {}),
            ),
          );
          await tester.pumpAndSettle();

          // 1. Sumidos -> perigo
          final sumidosCard = findCardAncestor(
            tester,
            find.text('BR0001 — Nelore'),
          );
          expect(
            sumidosCard.shape,
            isA<RoundedRectangleBorder>(),
            reason: 'Card de sumidos deve ter RoundedRectangleBorder',
          );
          final sumidosBorder = sumidosCard.shape! as RoundedRectangleBorder;
          expect(sumidosBorder.side.color, tokens['perigo']);
          expect(sumidosBorder.side.width, 1.5);
          expect(sumidosBorder.borderRadius, BorderRadius.circular(16));

          // 2. Carência -> atencao
          final carenciaCard = findCardAncestor(
            tester,
            find.text('BR0002 — Angus'),
          );
          expect(
            carenciaCard.shape,
            isA<RoundedRectangleBorder>(),
            reason: 'Card de carencia deve ter RoundedRectangleBorder',
          );
          final carenciaBorder = carenciaCard.shape! as RoundedRectangleBorder;
          expect(carenciaBorder.side.color, tokens['atencao']);
          expect(carenciaBorder.side.width, 1.5);
          expect(carenciaBorder.borderRadius, BorderRadius.circular(16));

          // 3. Prontos para Abate -> sem borda colorida (shape nulo)
          final prontosCard = findCardAncestor(
            tester,
            find.text('BR0003 — Nelore'),
          );
          expect(
            prontosCard.shape,
            isNull,
            reason: 'Card de prontos para abate deve manter shape nulo (padrão)',
          );

          // 4. Estoque Abaixo do Mínimo -> atencao
          final estoqueFinder = find.text('Sal mineral');
          await tester.scrollUntilVisible(
            estoqueFinder,
            300,
            scrollable: find.byType(Scrollable).first,
          );
          final estoqueCard = findCardAncestor(tester, estoqueFinder);
          expect(
            estoqueCard.shape,
            isA<RoundedRectangleBorder>(),
            reason: 'Card de estoque baixo deve ter RoundedRectangleBorder',
          );
          final estoqueBorder = estoqueCard.shape! as RoundedRectangleBorder;
          expect(estoqueBorder.side.color, tokens['atencao']);
          expect(estoqueBorder.side.width, 1.5);
          expect(estoqueBorder.borderRadius, BorderRadius.circular(16));

          // 5. Baixo Desempenho -> sem borda colorida (shape nulo)
          final baixoDesempenhoFinder = find.text('BR0004 — Brahman');
          await tester.scrollUntilVisible(
            baixoDesempenhoFinder,
            300,
            scrollable: find.byType(Scrollable).first,
          );
          final baixoDesempenhoCard = findCardAncestor(
            tester,
            baixoDesempenhoFinder,
          );
          expect(
            baixoDesempenhoCard.shape,
            isNull,
            reason: 'Card de baixo desempenho deve manter shape nulo (padrão)',
          );
        },
      );
    }
  });

  group('Spec 0087 - Critério 4: borda de _RecomendacaoCard com AppColors', () {
    for (final isDark in [false, true]) {
      final themeName = isDark ? 'dark' : 'light';
      final tokens = isDark ? AppColors.dark : AppColors.light;
      final themeData = isDark ? AppThemes.dark : AppThemes.light;

      testWidgets(
        'cards de recomendação alta, media e baixa usam perigo, atencao e sucesso ($themeName)',
        (tester) async {
          final client = MockClient((request) async {
            if (request.url.path == '/alertas') {
              return _json({'sumidos': [], 'carencia': [], 'prontos_para_abate': [], 'estoque_baixo': [], 'baixo_desempenho': []});
            }
            if (request.url.path == '/recomendacoes') {
              return _json(_recomendacoesPayload());
            }
            return _json({'detail': 'Not found'}, status: 404);
          });

          final api = ApiClient(
            tokenStore: _TestTokenStore(),
            httpClient: client,
            baseUrl: 'http://mock.local',
          );

          await tester.pumpWidget(
            MaterialApp(
              theme: themeData,
              home: AlertsPage(api: api, onUnauthorized: () {}),
            ),
          );
          await tester.pumpAndSettle();

          // Alta -> perigo
          final altaCard = findCardAncestor(
            tester,
            find.text('Estoque crítico de ração'),
          );
          final altaBorder = altaCard.shape! as RoundedRectangleBorder;
          expect(altaBorder.side.color, tokens['perigo']);
          expect(altaBorder.side.width, 1.5);

          // Media -> atencao
          final mediaCard = findCardAncestor(
            tester,
            find.text('GMD abaixo da meta'),
          );
          final mediaBorder = mediaCard.shape! as RoundedRectangleBorder;
          expect(mediaBorder.side.color, tokens['atencao']);
          expect(mediaBorder.side.width, 1.5);

          // Baixa -> sucesso
          final baixaCard = findCardAncestor(
            tester,
            find.text('Atenção ao calendário'),
          );
          final baixaBorder = baixaCard.shape! as RoundedRectangleBorder;
          expect(baixaBorder.side.color, tokens['sucesso']);
          expect(baixaBorder.side.width, 1.5);
        },
      );
    }
  });
}
