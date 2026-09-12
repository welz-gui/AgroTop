import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:agrotop_mobile/screens/dashboard_resumo_page.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _MemoryTokenStore implements TokenStore {
  StoredTokens? _tokens = const StoredTokens(
    accessToken: 'access-live',
    refreshToken: 'refresh-valid',
  );

  @override
  Future<void> clear() async => _tokens = null;

  @override
  Future<StoredTokens?> read() async => _tokens;

  @override
  Future<void> write(StoredTokens value) async => _tokens = value;
}

http.Response _json(Object body, {int status = 200}) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

ApiClient _api(MockClient client) => ApiClient(
  tokenStore: _MemoryTokenStore(),
  baseUrl: 'http://mock.local',
  httpClient: client,
);

Future<void> _openDrawer(WidgetTester tester) async {
  await tester.tap(find.byTooltip('Open navigation menu'));
  await tester.pumpAndSettle();
}

Future<void> _tapDrawerItem(WidgetTester tester, String key) async {
  final item = find.byKey(ValueKey<String>(key));
  await tester.ensureVisible(item);
  await tester.tap(item);
  await tester.pumpAndSettle();
}

Map<String, dynamic> _resumo({
  int total = 12,
  double peso = 412.5,
  double gmd = 0.65,
  double arrobas = 28.4,
  double lotacao = 1.25,
  int machos = 7,
  int femeas = 5,
  int sumidos = 1,
  int carencia = 2,
  int prontos = 3,
  List<Map<String, dynamic>>? distribuicao,
}) => {
  'total_animais': total,
  'peso_medio_kg': peso,
  'gmd_medio_kg_dia': gmd,
  'arrobas_produzidas': arrobas,
  'lotacao_ua_ha': lotacao,
  'machos': machos,
  'femeas': femeas,
  'distribuicao_por_raca':
      distribuicao ??
      const [
        {'raca': 'Nelore', 'quantidade': 7},
        {'raca': 'Angus', 'quantidade': 3},
        {'raca': 'Brangus', 'quantidade': 2},
      ],
  'alertas': {
    'sumidos': sumidos,
    'carencia': carencia,
    'prontos_para_abate': prontos,
  },
};

const _tresRacas = [
  {'raca': 'Nelore', 'quantidade': 7},
  {'raca': 'Angus', 'quantidade': 3},
  {'raca': 'Brangus', 'quantidade': 2},
];

Map<String, dynamic> _emptyAlerts() => {
  'sumidos': [],
  'carencia': [],
  'prontos_para_abate': [],
  'estoque_baixo': [],
  'baixo_desempenho': [],
};

void main() {
  testWidgets('abre o resumo a partir de AnimalsPage e exibe KPIs e alertas', (
    tester,
  ) async {
    final api = _api(
      MockClient((request) async {
        if (request.url.path == '/animais' ||
            request.url.path == '/trato/pendentes') {
          return _json([]);
        }
        if (request.url.path == '/alertas') return _json(_emptyAlerts());
        if (request.url.path == '/dashboard/resumo') return _json(_resumo());
        return _json({'detail': 'Não encontrado'}, status: 404);
      }),
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

    await _openDrawer(tester);
    await _tapDrawerItem(tester, 'open-dashboard-resumo');

    expect(find.byType(DashboardResumoPage), findsOneWidget);
    expect(
      find.byKey(const ValueKey('dashboard-kpi-total-animais')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('dashboard-kpi-peso-medio')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('dashboard-kpi-gmd-medio')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('dashboard-kpi-arrobas-produzidas')),
      findsOneWidget,
    );
    expect(find.byKey(const ValueKey('dashboard-kpi-lotacao')), findsOneWidget);
    expect(find.byKey(const ValueKey('dashboard-kpi-machos')), findsOneWidget);
    expect(find.byKey(const ValueKey('dashboard-kpi-femeas')), findsOneWidget);
    expect(find.text('412,5 kg'), findsOneWidget);
    expect(find.text('0,650 kg/dia'), findsOneWidget);
    expect(find.text('28,4 @'), findsOneWidget);
    final scrollable = find.byKey(const ValueKey('dashboard-resumo-list'));
    await tester.dragUntilVisible(
      find.byKey(const ValueKey('dashboard-alert-sumidos')),
      scrollable,
      const Offset(0, -120),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey('dashboard-alert-sumidos')),
      findsOneWidget,
    );
    await tester.dragUntilVisible(
      find.byKey(const ValueKey('dashboard-alert-carencia')),
      scrollable,
      const Offset(0, -120),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey('dashboard-alert-carencia')),
      findsOneWidget,
    );
    await tester.dragUntilVisible(
      find.byKey(const ValueKey('dashboard-alert-prontos')),
      scrollable,
      const Offset(0, -120),
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const ValueKey('dashboard-alert-prontos')),
      findsOneWidget,
    );
  });

  testWidgets('resumo vazio explica que não há animais cadastrados', (
    tester,
  ) async {
    final api = _api(
      MockClient((request) async {
        expect(request.url.path, '/dashboard/resumo');
        return _json(
          _resumo(total: 0, peso: 0, gmd: 0, arrobas: 0, lotacao: 0),
        );
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: DashboardResumoPage(api: api, onUnauthorized: () {}),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey('dashboard-empty-message')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('dashboard-kpi-total-animais')),
      findsNothing,
    );
  });

  test('RacaContagem.fromJson lê o payload da API', () {
    final raca = RacaContagem.fromJson(const {
      'raca': 'Nelore',
      'quantidade': 7,
    });

    expect(raca.raca, 'Nelore');
    expect(raca.quantidade, 7);
  });

  test('AppColors.series mantém a paleta categórica da fonte web', () {
    expect(AppColors.series.map((color) => color.toARGB32()).toList(), const [
      0xFF4ADE80,
      0xFF22D3EE,
      0xFFFBBF24,
      0xFFA78BFA,
      0xFFF87171,
      0xFF34D399,
      0xFF60A5FA,
      0xFFFB923C,
      0xFFF472B6,
      0xFFFACC15,
    ]);
  });

  testWidgets('gráfico por raça mostra legenda nos três temas', (tester) async {
    expect(
      DashboardResumo.fromJson(
        _resumo(distribuicao: _tresRacas),
      ).distribuicaoPorRaca,
      hasLength(3),
    );
    final api = _api(
      MockClient((request) async => _json(_resumo(distribuicao: _tresRacas))),
    );

    for (final mode in ThemeMode.values) {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppThemes.light,
          darkTheme: AppThemes.dark,
          themeMode: mode,
          home: DashboardResumoPage(
            key: ValueKey(mode),
            api: api,
            onUnauthorized: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('12'), findsOneWidget);
      await tester.dragUntilVisible(
        find.byKey(const ValueKey('dashboard-breed-donut')),
        find.byKey(const ValueKey('dashboard-resumo-list')),
        const Offset(0, -120),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('dashboard-breed-donut')),
        findsOneWidget,
      );
      expect(find.text('Nelore (7)'), findsOneWidget);
      expect(find.text('Angus (3)'), findsOneWidget);
      expect(find.text('Brangus (2)'), findsOneWidget);
    }
  });

  testWidgets('distribuição vazia mantém o restante do resumo', (tester) async {
    final api = _api(
      MockClient((request) async => _json(_resumo(distribuicao: const []))),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: DashboardResumoPage(api: api, onUnauthorized: () {}),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('dashboard-breed-donut')), findsNothing);
    expect(
      find.byKey(const ValueKey('dashboard-kpi-total-animais')),
      findsOneWidget,
    );
  });

  testWidgets('pull-to-refresh recarrega o resumo com novos dados', (
    tester,
  ) async {
    var requests = 0;
    final api = _api(
      MockClient((request) async {
        expect(request.url.path, '/dashboard/resumo');
        requests++;
        return _json(_resumo(total: requests == 1 ? 12 : 15));
      }),
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: AppThemes.light,
        home: DashboardResumoPage(api: api, onUnauthorized: () {}),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('12'), findsOneWidget);

    await tester.fling(
      find.byKey(const ValueKey('dashboard-resumo-list')),
      const Offset(0, 400),
      1000,
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();

    expect(requests, 2);
    expect(find.text('15'), findsOneWidget);
  });

  testWidgets(
    'Spec 0090: pull-to-refresh com erro 500 mantém dados antigos e exibe SnackBar',
    (tester) async {
      var requests = 0;
      final api = _api(
        MockClient((request) async {
          expect(request.url.path, '/dashboard/resumo');
          requests++;
          if (requests == 1) {
            return _json(_resumo(total: 12));
          }
          return _json(
            {'detail': 'Falha interna ao atualizar resumo'},
            status: 500,
          );
        }),
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppThemes.light,
          home: DashboardResumoPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('12'), findsOneWidget);

      await tester.fling(
        find.byKey(const ValueKey('dashboard-resumo-list')),
        const Offset(0, 400),
        1000,
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();

      expect(requests, 2);
      // Dados antigos continuam visíveis
      expect(find.text('12'), findsOneWidget);
      // SnackBar exibido com mensagem de erro da API
      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.text('Falha interna ao atualizar resumo'), findsOneWidget);
    },
  );

  testWidgets(
    'Spec 0090: pull-to-refresh com erro de rede mantém dados antigos e exibe SnackBar genérico',
    (tester) async {
      var requests = 0;
      final api = _api(
        MockClient((request) async {
          expect(request.url.path, '/dashboard/resumo');
          requests++;
          if (requests == 1) {
            return _json(_resumo(total: 12));
          }
          throw http.ClientException('Falha de conexão com o servidor');
        }),
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppThemes.light,
          home: DashboardResumoPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('12'), findsOneWidget);

      await tester.fling(
        find.byKey(const ValueKey('dashboard-resumo-list')),
        const Offset(0, 400),
        1000,
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();

      expect(requests, 2);
      // Dados antigos continuam visíveis
      expect(find.text('12'), findsOneWidget);
      // SnackBar exibido com mensagem genérica de rede
      expect(find.byType(SnackBar), findsOneWidget);
      expect(
        find.text('API indisponível. Tente carregar o resumo novamente.'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'Spec 0090: falha na carga inicial continua mostrando _LoadError em tela cheia',
    (tester) async {
      final api = _api(
        MockClient((request) async {
          expect(request.url.path, '/dashboard/resumo');
          return _json({'detail': 'Falha na carga inicial'}, status: 500);
        }),
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppThemes.light,
          home: DashboardResumoPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      // Tela de erro com botão retry
      expect(find.text('Falha na carga inicial'), findsOneWidget);
      expect(find.text('Tentar novamente'), findsOneWidget);
      // Nenhum card do dashboard é renderizado
      expect(
        find.byKey(const ValueKey('dashboard-kpi-total-animais')),
        findsNothing,
      );
      // Nenhum SnackBar exibido na carga inicial
      expect(find.byType(SnackBar), findsNothing);
    },
  );
}
