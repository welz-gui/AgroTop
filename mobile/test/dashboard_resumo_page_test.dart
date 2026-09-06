import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:agrotop_mobile/screens/dashboard_resumo_page.dart';
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
}) => {
  'total_animais': total,
  'peso_medio_kg': peso,
  'gmd_medio_kg_dia': gmd,
  'arrobas_produzidas': arrobas,
  'lotacao_ua_ha': lotacao,
  'machos': machos,
  'femeas': femeas,
  'alertas': {
    'sumidos': sumidos,
    'carencia': carencia,
    'prontos_para_abate': prontos,
  },
};

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

    await tester.tap(find.byKey(const ValueKey('open-dashboard-resumo')));
    await tester.pumpAndSettle();

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
}
