import 'dart:convert';
import 'dart:io';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/models.dart';
import 'package:agrotop_mobile/offline_queue.dart';
import 'package:agrotop_mobile/shallow_cache.dart';
import 'package:agrotop_mobile/screens/animal_photo_section.dart';
import 'package:agrotop_mobile/screens/alerts_page.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
import 'package:agrotop_mobile/screens/devices_page.dart';
import 'package:agrotop_mobile/screens/feeding_page.dart';
import 'package:agrotop_mobile/screens/medication_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:golden_toolkit/golden_toolkit.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

class GoldenTokenStore implements TokenStore {
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

Map<String, dynamic> _alertsResponse({required bool withItems}) {
  if (!withItems) {
    return {
      'sumidos': [],
      'carencia': [],
      'prontos_para_abate': [],
      'estoque_baixo': [],
      'baixo_desempenho': [],
    };
  }
  return {
    'sumidos': [
      {
        'animal_id': 'BR0099',
        'breed': 'Nelore',
        'lote_id': 'P01',
        'peso_atual': 401.2,
        'dias_sem_pesagem': 38,
      },
    ],
    'carencia': [
      {
        'animal_id': 'BR0098',
        'breed': 'Angus',
        'carencia_ate': '2026-09-19',
        'dias_restantes': 19,
      },
    ],
    'prontos_para_abate': [
      {
        'animal_id': 'BR0097',
        'breed': 'Nelore',
        'peso_atual': 510.0,
        'peso_alvo': 500.0,
        'arrobas': 17.68,
      },
    ],
    'estoque_baixo': [
      {
        'insumo_id': 8,
        'nome': 'Sal mineral',
        'estoque_atual': 5.0,
        'estoque_minimo': 10.0,
        'unidade': 'kg',
      },
    ],
    'baixo_desempenho': [
      {
        'animal_id': 'BR0096',
        'breed': 'Brahman',
        'lote_id': 'P02',
        'peso_atual': 355.0,
        'gmd': 0.31,
        'meta_gmd': 0.5,
      },
    ],
  };
}

MockClient _client({
  String? carenciaAte,
  List<Map<String, dynamic>>? aplicacoes,
  bool allFeedingsConfirmed = false,
  Map<String, dynamic>? alerts,
}) => MockClient((request) async {
  if (request.method == 'POST' && request.url.path == '/auth/login') {
    return _json({
      'access_token': 'access-live',
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
  if (request.method == 'GET' && request.url.path == '/alertas') {
    return _json(alerts ?? _alertsResponse(withItems: false));
  }
  if (request.url.path == '/animais') {
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
    return _json([
      {
        'plano_id': 101,
        'lote_id': 'P01',
        'lote_nome': 'Piquete Central',
        'produto': 'Sal mineral',
        'quantidade': 25.0,
        'unidade': 'kg',
        'frequencia': 'diário',
        'insumo_id': 8,
        'confirmado_no_periodo': allFeedingsConfirmed,
        'ultima_confirmacao': allFeedingsConfirmed ? '2026-08-25' : null,
      },
      {
        'plano_id': 102,
        'lote_id': 'P02',
        'lote_nome': 'Piquete Norte',
        'produto': 'Núcleo mineral',
        'quantidade': 8.0,
        'unidade': 'kg',
        'frequencia': 'semanal',
        'insumo_id': null,
        'confirmado_no_periodo': true,
        'ultima_confirmacao': '2026-08-25',
      },
    ]);
  }
  if (request.method == 'GET' &&
      request.url.path == '/animais/BR0001/medicamentos') {
    return _json({
      'carencia_ate': carenciaAte,
      'aplicacoes': aplicacoes ?? <Map<String, dynamic>>[],
    });
  }
  if (request.url.path == '/animais/BR0001') {
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
  if (request.method == 'GET' && request.url.path == '/protocolos') {
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
  if (request.method == 'GET' && request.url.path == '/animais/BR0001/fotos') {
    return _json([]);
  }
  if (request.method == 'GET' && request.url.path == '/lotes') {
    return _json([
      {
        'id': 'P01',
        'nome': 'Piquete Central',
        'capacidade_ua': 30.0,
        'animais_ativos': 18,
      },
      {
        'id': 'P02',
        'nome': 'Piquete Norte',
        'capacidade_ua': 24.5,
        'animais_ativos': 12,
      },
      {
        'id': 'P03',
        'nome': 'Piquete da Baixada',
        'capacidade_ua': null,
        'animais_ativos': 7,
      },
    ]);
  }
  if (request.method == 'POST' && request.url.path == '/animais/movimentar') {
    return _json({
      'movidos': ['BR0001'],
      'ja_no_destino': ['BR0002'],
      'erros': ['BR0003: animal bloqueado'],
    });
  }
  return _json({'detail': 'Não encontrado'}, status: 404);
});

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('telas principais são cobertas nos três modos de tema', (
    tester,
  ) async {
    final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
    if (captureGoldens) await loadAppFonts();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    for (final mode in ThemeMode.values) {
      SharedPreferences.setMockInitialValues({'theme_mode': mode.name});
      final preferences = await SharedPreferences.getInstance();
      final api = ApiClient(
        tokenStore: GoldenTokenStore(),
        httpClient: _client(),
        baseUrl: 'http://mock.local',
      );

      await tester.pumpWidget(
        AgroTopApp(preferences: preferences, apiClient: api),
      );
      await tester.pumpAndSettle();
      expect(
        tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode,
        mode,
      );
      expect(find.text('Gestão do rebanho'), findsOneWidget);
      if (captureGoldens) {
        await expectLater(
          find.byType(MaterialApp),
          matchesGoldenFile('goldens/${mode.name}-01-login.png'),
        );
      }

      await tester.enterText(find.byType(TextFormField).at(0), 'admin');
      await tester.enterText(find.byType(TextFormField).at(1), 'senha-segura');
      await tester.tap(find.text('Entrar'));
      await tester.pumpAndSettle();
      expect(find.text('BR0001'), findsOneWidget);
      if (captureGoldens) {
        await expectLater(
          find.byType(MaterialApp),
          matchesGoldenFile('goldens/${mode.name}-02-lista.png'),
        );
      }

      await tester.tap(find.text('BR0001'));
      await tester.pumpAndSettle();
      expect(find.text('382.4 kg'), findsOneWidget);
      expect(find.text('Sem restrição de carência'), findsOneWidget);
      if (captureGoldens) {
        await expectLater(
          find.byType(MaterialApp),
          matchesGoldenFile('goldens/${mode.name}-03-ficha.png'),
        );
      }

      final weighingButton = find.byKey(const ValueKey('open-weighing'));
      await tester.scrollUntilVisible(
        weighingButton,
        300,
        scrollable: find.byType(Scrollable).last,
      );
      await tester.tap(weighingButton);
      await tester.pumpAndSettle();
      expect(find.text('Pesagem BR0001'), findsOneWidget);
      if (captureGoldens) {
        await expectLater(
          find.byType(MaterialApp),
          matchesGoldenFile('goldens/${mode.name}-04-pesagem.png'),
        );
      }

      await tester.pageBack();
      await tester.pumpAndSettle();
      final movementButton = find.byKey(const ValueKey('open-movement'));
      await tester.scrollUntilVisible(
        movementButton,
        300,
        scrollable: find.byType(Scrollable).last,
      );
      await tester.tap(movementButton);
      await tester.pumpAndSettle();
      expect(find.text('Piquete de destino'), findsOneWidget);
      if (captureGoldens) {
        await expectLater(
          find.byType(MaterialApp),
          matchesGoldenFile('goldens/${mode.name}-05-destino.png'),
        );
      }

      await tester.tap(find.byKey(const ValueKey('movement-lote-P02')));
      final confirmButton = find.byKey(const ValueKey('confirm-movement'));
      await tester.scrollUntilVisible(
        confirmButton,
        300,
        scrollable: find.byType(Scrollable).last,
      );
      await tester.tap(confirmButton);
      await tester.pumpAndSettle();
      expect(find.text('Resultado da movimentação'), findsOneWidget);
      if (captureGoldens) {
        await expectLater(
          find.byType(MaterialApp),
          matchesGoldenFile('goldens/${mode.name}-06-resultado.png'),
        );
      }

      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
    }
  });

  testWidgets('seção de sanidade com e sem carência ativa nos três temas', (
    tester,
  ) async {
    final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
    if (captureGoldens) await loadAppFonts();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    for (final mode in ThemeMode.values) {
      for (final comCarencia in [true, false]) {
        final tokenStore = GoldenTokenStore()
          ..tokens = const StoredTokens(
            accessToken: 'access-live',
            refreshToken: 'refresh-valid',
          );

        final api = ApiClient(
          tokenStore: tokenStore,
          httpClient: comCarencia
              ? _client(
                  carenciaAte: '2026-09-19',
                  aplicacoes: [
                    {
                      'medicamento': 'Ivermectina 1%',
                      'dose': 8.0,
                      'unidade': 'ml',
                      'via': 'Subcutânea',
                      'carencia_dias': 28,
                      'data': '2026-08-22',
                      'protocolo_id': 1,
                    },
                  ],
                )
              : _client(),
          baseUrl: 'http://mock.local',
        );

        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.light(),
            darkTheme: ThemeData.dark(),
            themeMode: mode,
            home: AnimalDetailPage(
              api: api,
              id: 'BR0001',
              onUnauthorized: () {},
              onMovementCompleted: () {},
            ),
          ),
        );
        await tester.pumpAndSettle();
        if (comCarencia) {
          expect(find.text('Em carência até 2026-09-19'), findsOneWidget);
          expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
        } else {
          expect(find.text('Sem restrição de carência'), findsOneWidget);
        }

        final historyCard = find.byKey(
          const ValueKey('medications-history-card'),
        );
        await tester.scrollUntilVisible(
          historyCard,
          300,
          scrollable: find.byType(Scrollable).first,
        );
        expect(
          find.text(
            comCarencia
                ? 'Histórico de aplicações (1)'
                : 'Histórico de aplicações (0)',
          ),
          findsOneWidget,
        );
        if (captureGoldens) {
          await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
              'goldens/${mode.name}-09-sanidade-ficha-${comCarencia ? 'com' : 'sem'}-carencia.png',
            ),
          );
        }

        // Tela de registrar medicamento (SanidadePage / MedicationPage)
        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.light(),
            darkTheme: ThemeData.dark(),
            themeMode: mode,
            home: MedicationPage(
              api: api,
              animalId: 'BR0001',
              onUnauthorized: () {},
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Sanidade BR0001'), findsOneWidget);
        expect(find.text('Protocolo sanitário'), findsOneWidget);
        if (captureGoldens) {
          await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
              'goldens/${mode.name}-10-sanidade-medicamento-${comCarencia ? 'com' : 'sem'}-carencia.png',
            ),
          );
        }

        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpAndSettle();
      }
    }
  });

  testWidgets('galeria vazia e com foto são cobertas nos três temas', (
    tester,
  ) async {
    final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
    if (captureGoldens) await loadAppFonts();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final image = File(
      'android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png',
    ).readAsBytesSync();

    for (final mode in ThemeMode.values) {
      for (final withPhoto in [false, true]) {
        final store = GoldenTokenStore()
          ..tokens = const StoredTokens(
            accessToken: 'access-live',
            refreshToken: 'refresh-valid',
          );
        final api = ApiClient(
          tokenStore: store,
          baseUrl: 'http://mock.local',
          httpClient: MockClient((request) async {
            if (request.url.path == '/animais/BR0001/fotos') {
              return _json(
                withPhoto
                    ? [
                        {
                          'id': 1,
                          'taken_date': '2026-08-23',
                          'mime': 'image/jpeg',
                        },
                      ]
                    : [],
              );
            }
            if (request.url.path == '/fotos/1') {
              return http.Response.bytes(
                image,
                200,
                headers: {'content-type': 'image/jpeg'},
              );
            }
            return _json({'detail': 'Não encontrado'}, status: 404);
          }),
        );

        await tester.pumpWidget(
          MaterialApp(
            debugShowCheckedModeBanner: false,
            theme: AppThemes.light,
            darkTheme: AppThemes.dark,
            themeMode: mode,
            home: Scaffold(
              body: SafeArea(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: AnimalPhotoSection(
                    api: api,
                    animalId: 'BR0001',
                    onUnauthorized: () {},
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        if (withPhoto) {
          final photoFinder = find.byKey(const ValueKey('animal-photo-1'));
          final imageWidget = tester.widget<Image>(photoFinder);
          await tester.runAsync(
            () => precacheImage(imageWidget.image, tester.element(photoFinder)),
          );
          await tester.pumpAndSettle();
        }
        expect(
          find.byKey(
            ValueKey(
              withPhoto ? 'animal-photo-gallery' : 'empty-photo-gallery',
            ),
          ),
          findsOneWidget,
        );
        if (withPhoto) {
          expect(find.byKey(const ValueKey('animal-photo-1')), findsOneWidget);
        }
        if (captureGoldens) {
          await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
              'goldens/${mode.name}-${withPhoto ? '08-fotos' : '07-fotos-vazia'}.png',
            ),
          );
        }
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpAndSettle();
      }
    }
  });

  testWidgets('trato pendente e tudo confirmado são cobertos nos três temas', (
    tester,
  ) async {
    final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
    if (captureGoldens) await loadAppFonts();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    for (final mode in ThemeMode.values) {
      for (final allConfirmed in [false, true]) {
        final store = GoldenTokenStore()
          ..tokens = const StoredTokens(
            accessToken: 'access-live',
            refreshToken: 'refresh-valid',
          );
        final api = ApiClient(
          tokenStore: store,
          baseUrl: 'http://mock.local',
          httpClient: _client(allFeedingsConfirmed: allConfirmed),
        );
        await tester.pumpWidget(
          MaterialApp(
            debugShowCheckedModeBanner: false,
            theme: AppThemes.light,
            darkTheme: AppThemes.dark,
            themeMode: mode,
            home: FeedingPage(api: api, onUnauthorized: () {}),
          ),
        );
        await tester.pumpAndSettle();
        expect(
          find.text(
            allConfirmed ? 'Tudo confirmado' : '1 item(ns) pendente(s)',
          ),
          findsOneWidget,
        );
        if (captureGoldens) {
          await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
              'goldens/${mode.name}-${allConfirmed ? '12-trato-confirmado' : '11-trato-pendentes'}.png',
            ),
          );
        }
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpAndSettle();
      }
    }
  });

  testWidgets('alertas vazios e com itens são cobertos nos três temas', (
    tester,
  ) async {
    final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
    if (captureGoldens) await loadAppFonts();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    for (final mode in ThemeMode.values) {
      for (final withItems in [false, true]) {
        final store = GoldenTokenStore()
          ..tokens = const StoredTokens(
            accessToken: 'access-live',
            refreshToken: 'refresh-valid',
          );
        final api = ApiClient(
          tokenStore: store,
          baseUrl: 'http://mock.local',
          httpClient: _client(alerts: _alertsResponse(withItems: withItems)),
        );
        await tester.pumpWidget(
          MaterialApp(
            debugShowCheckedModeBanner: false,
            theme: AppThemes.light,
            darkTheme: AppThemes.dark,
            themeMode: mode,
            home: AlertsPage(api: api, onUnauthorized: () {}),
          ),
        );
        await tester.pumpAndSettle();

        expect(
          find.text(
            withItems ? '🔴 Animais Sumidos (1)' : '🔴 Animais Sumidos (0)',
          ),
          findsOneWidget,
        );
        expect(
          find.text('📉 Baixo Desempenho (${withItems ? 1 : 0})'),
          findsOneWidget,
        );
        if (withItems) {
          expect(find.text('BR0099 — Nelore'), findsOneWidget);
          expect(find.text('Sal mineral'), findsOneWidget);
        } else {
          expect(find.text('✅ Nenhum animal sumido.'), findsOneWidget);
          expect(
            find.text('✅ Todos os insumos com estoque adequado.'),
            findsOneWidget,
          );
        }

        if (captureGoldens) {
          await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
              'goldens/${mode.name}-${withItems ? '17-alertas-com-itens' : '16-alertas-vazios'}.png',
            ),
          );
        }
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpAndSettle();
      }
    }
  });

  testWidgets(
    'indicador de pendências na fila offline (vazia e com itens) nos três temas',
    (tester) async {
      final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
      if (captureGoldens) await loadAppFonts();
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      for (final mode in ThemeMode.values) {
        for (final withPending in [false, true]) {
          final store = GoldenTokenStore()
            ..tokens = const StoredTokens(
              accessToken: 'access-live',
              refreshToken: 'refresh-valid',
            );
          final api = ApiClient(
            tokenStore: store,
            baseUrl: 'http://mock.local',
            httpClient: _client(allFeedingsConfirmed: true),
          );
          final queue = OfflineQueue(storage: MemoryQueueStorage());
          if (withPending) {
            await queue.enqueueWeighing(
              animalId: 'BR0001',
              peso: 410.0,
              data: '2026-08-27',
            );
          }

          await tester.pumpWidget(
            MaterialApp(
              debugShowCheckedModeBanner: false,
              theme: AppThemes.light,
              darkTheme: AppThemes.dark,
              themeMode: mode,
              home: AnimalsPage(
                api: api,
                themeMode: mode,
                onThemeChanged: (_) {},
                onUnauthorized: () {},
                offlineQueue: queue,
              ),
            ),
          );
          await tester.pumpAndSettle();

          expect(
            find.byKey(const ValueKey('sync-queue-button')),
            findsOneWidget,
          );
          if (withPending) {
            expect(
              find.byKey(const ValueKey('pending-queue-badge')),
              findsOneWidget,
            );
            expect(find.text('1'), findsOneWidget);
          } else {
            expect(
              find.byKey(const ValueKey('pending-queue-badge')),
              findsNothing,
            );
          }

          if (captureGoldens) {
            await expectLater(
              find.byType(MaterialApp),
              matchesGoldenFile(
                'goldens/${mode.name}-${withPending ? '14-fila-offline-com-itens' : '13-fila-offline-vazia'}.png',
              ),
            );
          }
          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pumpAndSettle();
        }
      }
    },
  );

  testWidgets('banner de dados cacheados desatualizados nos três temas', (
    tester,
  ) async {
    final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
    if (captureGoldens) await loadAppFonts();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    for (final mode in ThemeMode.values) {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final shallowCache = ShallowCache(prefs);
      await shallowCache.saveAnimals([
        const AnimalSummary(
          id: 'BR0001',
          breed: 'Nelore',
          sex: 'M',
          currentWeight: 382.4,
          loteId: 'P01',
        ),
      ]);

      final store = GoldenTokenStore()
        ..tokens = const StoredTokens(
          accessToken: 'access-live',
          refreshToken: 'refresh-valid',
        );
      // Cliente que simula falha de conexão
      final api = ApiClient(
        tokenStore: store,
        baseUrl: 'http://mock.local',
        httpClient: MockClient((request) async {
          throw http.ClientException('Conexão indisponível');
        }),
      );

      await tester.pumpWidget(
        MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: AppThemes.light,
          darkTheme: AppThemes.dark,
          themeMode: mode,
          home: AnimalsPage(
            api: api,
            themeMode: mode,
            onThemeChanged: (_) {},
            onUnauthorized: () {},
            shallowCache: shallowCache,
            offlineQueue: OfflineQueue(storage: MemoryQueueStorage()),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const ValueKey('offline-cache-banner')),
        findsOneWidget,
      );
      expect(find.textContaining('pode estar desatualizado'), findsOneWidget);
      expect(find.text('BR0001'), findsOneWidget);

      if (captureGoldens) {
        await expectLater(
          find.byType(MaterialApp),
          matchesGoldenFile(
            'goldens/${mode.name}-15-cache-desatualizado-banner.png',
          ),
        );
      }
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
    }
  });

  testWidgets('tela de brincos cobre busca e motivo nos três temas', (
    tester,
  ) async {
    final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
    if (captureGoldens) await loadAppFonts();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    for (final mode in ThemeMode.values) {
      for (final view in ['vazia', 'nao-encontrado', 'encontrado', 'motivo']) {
        final store = GoldenTokenStore()
          ..tokens = const StoredTokens(
            accessToken: 'access-live',
            refreshToken: 'refresh-valid',
          );
        final api = ApiClient(
          tokenStore: store,
          baseUrl: 'http://mock.local',
          httpClient: MockClient((request) async {
            if (request.url.path.endsWith('BR-404')) {
              return _json({'detail': 'Ausente'}, status: 404);
            }
            return _json({
              'id': 'device-1',
              'codigo_visual': 'BR-100',
              'tipo': 'brinco_visual',
              'status': 'recebido',
              'lote': 'Lote Norte',
              'transicoes_permitidas': [
                {
                  'para': view == 'motivo' ? 'danificado' : 'disponivel',
                  'exige_motivo': view == 'motivo',
                  'exige_autorizacao': false,
                },
              ],
            });
          }),
        );
        await tester.pumpWidget(
          MaterialApp(
            debugShowCheckedModeBanner: false,
            theme: AppThemes.light,
            darkTheme: AppThemes.dark,
            themeMode: mode,
            home: DevicesPage(api: api, onUnauthorized: () {}),
          ),
        );
        await tester.pumpAndSettle();
        if (view != 'vazia') {
          await tester.enterText(
            find.byKey(const ValueKey('device-code-field')),
            view == 'nao-encontrado' ? 'BR-404' : 'BR-100',
          );
          await tester.tap(find.byKey(const ValueKey('search-device')));
          await tester.pumpAndSettle();
        }
        if (view == 'motivo') {
          await tester.tap(
            find.byKey(const ValueKey('device-transition-danificado')),
          );
          await tester.pumpAndSettle();
        }
        if (captureGoldens) {
          await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
              'goldens/${mode.name}-${switch (view) {
                'vazia' => '18-brincos-vazia',
                'nao-encontrado' => '19-brincos-nao-encontrado',
                'encontrado' => '20-brincos-encontrado',
                _ => '21-brincos-motivo',
              }}.png',
            ),
          );
        }
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpAndSettle();
      }
    }
  });
}
