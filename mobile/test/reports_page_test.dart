import 'dart:convert';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:agrotop_mobile/screens/reports_page.dart';
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

List<Map<String, dynamic>> _mockInventario() => [
      {
        'id': 'BR0001',
        'raca': 'Nelore',
        'sexo': 'M',
        'categoria_idade': '13 a 24 meses',
        'idade_display': '18 meses',
        'data_nascimento': '2025-03-01',
        'nascimento_estimado': false,
        'origem_idade': 'propriedade',
        'data_entrada': '2025-09-01',
        'peso_entrada_kg': 280.0,
        'peso_atual_kg': 420.5,
        'ganho_kg': 140.5,
        'arrobas_atuais': 14.02,
        'gmd_kg_dia': 0.75,
        'status': 'ativo',
        'lote_id': 'P01',
        'fornecedor': 'Fazenda Primavera',
        'nf': '12345',
        'gta': '98765',
        'carencia_ate': null,
      },
      {
        'id': 'BR0002',
        'raca': 'Angus',
        'sexo': 'F',
        'categoria_idade': '25 a 36 meses',
        'idade_display': '26 meses (est.)',
        'data_nascimento': '2024-07-15',
        'nascimento_estimado': true,
        'origem_idade': 'estimado',
        'data_entrada': '2025-01-10',
        'peso_entrada_kg': 310.0,
        'peso_atual_kg': 465.0,
        'ganho_kg': 155.0,
        'arrobas_atuais': 15.5,
        'gmd_kg_dia': null,
        'status': 'carencia',
        'lote_id': 'P02',
        'fornecedor': 'Cabanha Estrela',
        'nf': '54321',
        'gta': '11223',
        'carencia_ate': '2026-09-20',
      },
      {
        'id': 'BR0003',
        'raca': 'Brahman',
        'sexo': 'M',
        'categoria_idade': 'Até 12 meses',
        'idade_display': '10 meses',
        'data_nascimento': '2025-11-01',
        'nascimento_estimado': false,
        'origem_idade': 'propriedade',
        'data_entrada': '2026-02-01',
        'peso_entrada_kg': 210.0,
        'peso_atual_kg': 320.0,
        'ganho_kg': 110.0,
        'arrobas_atuais': 10.67,
        'gmd_kg_dia': 0.62,
        'status': 'ativo',
        'lote_id': 'P01',
        'fornecedor': null,
        'nf': null,
        'gta': null,
        'carencia_ate': null,
      },
    ];

List<Map<String, dynamic>> _mockPesagens() => [
      {
        'animal_id': 'BR0001',
        'data': '2026-09-01',
        'peso_kg': 420.5,
        'metodo': 'pesado',
        'lote_id': 'P01',
        'operador': 'João Silva',
        'observacoes': 'Pesagem de rotina no brete',
      },
      {
        'animal_id': 'BR0002',
        'data': '2026-08-28',
        'peso_kg': 465.0,
        'metodo': 'estimado',
        'lote_id': 'P02',
        'operador': 'Carlos Souza',
        'observacoes': null,
      },
      {
        'animal_id': 'BR0003',
        'data': '2026-08-25',
        'peso_kg': 320.0,
        'metodo': 'medicao',
        'lote_id': 'P01',
        'operador': 'João Silva',
        'observacoes': 'Medição por fita',
      },
    ];

void main() {
  testWidgets(
    'Critério 2: abrir tela de relatórios a partir de AnimalsPage -> inventário -> pesagens traduzidas',
    (tester) async {
      final client = MockClient((request) async {
        if (request.url.path == '/animais') {
          return _json([
            {
              'id': 'BR0001',
              'breed': 'Nelore',
              'sex': 'M',
              'current_weight': 420.5,
              'status': 'ativo',
              'lote_id': 'P01',
              'birth_date': '2025-03-01',
              'animal_uuid': 'uuid-1',
            }
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
        if (request.url.path == '/relatorios/inventario') {
          return _json(_mockInventario());
        }
        if (request.url.path == '/relatorios/pesagens') {
          return _json(_mockPesagens());
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

      // 1. Abre tela de relatórios pelo botão do AppBar
      final reportsButton = find.byKey(const ValueKey('open-reports'));
      expect(reportsButton, findsOneWidget);
      await tester.tap(reportsButton);
      await tester.pumpAndSettle();

      expect(find.text('Relatórios'), findsOneWidget);
      expect(find.byKey(const ValueKey('tab-inventario')), findsOneWidget);
      expect(find.byKey(const ValueKey('tab-pesagens')), findsOneWidget);

      // 2. Aba Inventário mostra animais do mock
      expect(find.text('BR0001'), findsOneWidget);
      expect(find.text('BR0002'), findsOneWidget);
      expect(find.text('BR0003'), findsOneWidget);

      // 3. Critério 3: gmd_kg_dia: null mostra '—', não 'null' e não '0.0'
      expect(find.textContaining('GMD: —'), findsOneWidget);
      expect(find.textContaining('GMD: null'), findsNothing);
      expect(find.textContaining('GMD: 0.0'), findsNothing);

      // 4. Critério 4: nascimento_estimado: true tem indicador visual '(est.)'
      expect(find.text('(est.)'), findsOneWidget);

      // Testa expansão de item do inventário
      await tester.tap(find.text('BR0001'));
      await tester.pumpAndSettle();
      expect(find.text('Fazenda Primavera'), findsOneWidget);
      expect(find.text('NF: 12345 / GTA: 98765'), findsOneWidget);

      // 5. Trocar para a aba Pesagens
      await tester.tap(find.byKey(const ValueKey('tab-pesagens')));
      await tester.pumpAndSettle();

      // Mostra pesagens do mock
      expect(find.text('BR0001'), findsOneWidget);
      expect(find.text('BR0002'), findsOneWidget);
      expect(find.text('BR0003'), findsOneWidget);

      // Métodos traduzidos
      expect(find.text('Pesado na balança'), findsOneWidget);
      expect(find.text('Estimado pelo operador'), findsOneWidget);
      expect(find.text('Estimado por medição (fita/fórmula)'), findsOneWidget);

      // Observações
      expect(find.text('Obs: Pesagem de rotina no brete'), findsOneWidget);
      expect(find.text('Obs: Medição por fita'), findsOneWidget);
    },
  );

  testWidgets('Filtro por status na aba de inventário', (tester) async {
    final client = MockClient((request) async {
      if (request.url.path == '/relatorios/inventario') {
        return _json(_mockInventario());
      }
      if (request.url.path == '/relatorios/pesagens') {
        return _json(_mockPesagens());
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
        home: ReportsPage(api: api, onUnauthorized: () {}),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('BR0001'), findsOneWidget);
    expect(find.text('BR0002'), findsOneWidget);
    expect(find.text('BR0003'), findsOneWidget);

    // Filtra por carência
    await tester.tap(find.byKey(const ValueKey('filter-carencia')));
    await tester.pumpAndSettle();

    expect(find.text('BR0001'), findsNothing);
    expect(find.text('BR0002'), findsOneWidget);
    expect(find.text('BR0003'), findsNothing);

    // Volta para todos
    await tester.tap(find.byKey(const ValueKey('filter-todos')));
    await tester.pumpAndSettle();

    expect(find.text('BR0001'), findsOneWidget);
    expect(find.text('BR0002'), findsOneWidget);
    expect(find.text('BR0003'), findsOneWidget);
  });

  group('ReportsPage com erros e 401', () {
    testWidgets('Chama onUnauthorized quando API retorna 401', (tester) async {
      bool unauthorizedCalled = false;
      final api = ApiClient(
        tokenStore: TestTokenStore(),
        baseUrl: 'http://mock.local',
        httpClient: MockClient((_) async => http.Response('Unauthorized', 401)),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ReportsPage(
            api: api,
            onUnauthorized: () => unauthorizedCalled = true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(unauthorizedCalled, isTrue);
    });

    testWidgets('Mostra erro e permite tentar novamente', (tester) async {
      int attempts = 0;
      final api = ApiClient(
        tokenStore: TestTokenStore(),
        baseUrl: 'http://mock.local',
        httpClient: MockClient((request) async {
          attempts++;
          if (attempts <= 2) {
            return http.Response(jsonEncode({'detail': 'Erro no servidor'}), 500);
          }
          if (request.url.path == '/relatorios/inventario') {
            return _json([
              {
                'id': 'BR9999',
                'raca': 'Nelore',
                'sexo': 'M',
                'categoria_idade': '13 a 24 meses',
                'idade_display': '15 meses',
                'data_nascimento': '2025-05-01',
                'nascimento_estimado': false,
                'origem_idade': 'propriedade',
                'data_entrada': '2025-10-01',
                'peso_entrada_kg': 250.0,
                'peso_atual_kg': 380.0,
                'ganho_kg': 130.0,
                'arrobas_atuais': 12.67,
                'gmd_kg_dia': 0.70,
                'status': 'ativo',
                'lote_id': 'P01',
                'fornecedor': null,
                'nf': null,
                'gta': null,
                'carencia_ate': null,
              }
            ]);
          }
          return _json([]);
        }),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ReportsPage(api: api, onUnauthorized: () {}),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Erro no servidor'), findsOneWidget);
      expect(find.text('Tentar novamente'), findsOneWidget);

      await tester.tap(find.text('Tentar novamente'));
      await tester.pumpAndSettle();

      expect(find.text('BR9999'), findsOneWidget);
    });
  });
}
