import 'dart:convert';
import 'dart:io';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app.dart';
import 'package:agrotop_mobile/app_colors.dart';
import 'package:agrotop_mobile/screens/animal_photo_section.dart';
import 'package:agrotop_mobile/screens/animals_page.dart';
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

MockClient _client({String? carenciaAte, List<Map<String, dynamic>>? aplicacoes}) =>
    MockClient((request) async {
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

  testWidgets('telas principais são cobertas nos três modos de tema', (tester) async {
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

  testWidgets('seção de sanidade com e sem carência ativa nos três temas', (tester) async {
    final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
    if (captureGoldens) await loadAppFonts();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    for (final mode in ThemeMode.values) {
      final tokenStore = GoldenTokenStore()
        ..tokens = const StoredTokens(
          accessToken: 'access-live',
          refreshToken: 'refresh-valid',
        );

      // Ficha COM carência ativa
      final apiComCarencia = ApiClient(
        tokenStore: tokenStore,
        httpClient: _client(
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
            }
          ],
        ),
        baseUrl: 'http://mock.local',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.light(),
          darkTheme: ThemeData.dark(),
          themeMode: mode,
          home: AnimalDetailPage(
            api: apiComCarencia,
            id: 'BR0001',
            onUnauthorized: () {},
            onMovementCompleted: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Em carência até 2026-09-19'), findsOneWidget);
      expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);

      final historyCard = find.byKey(const ValueKey('medications-history-card'));
      await tester.scrollUntilVisible(
        historyCard,
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Histórico de aplicações (1)'), findsOneWidget);

      // Tela de registrar medicamento (SanidadePage / MedicationPage)
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.light(),
          darkTheme: ThemeData.dark(),
          themeMode: mode,
          home: MedicationPage(
            api: apiComCarencia,
            animalId: 'BR0001',
            onUnauthorized: () {},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Sanidade BR0001'), findsOneWidget);
      expect(find.text('Protocolo sanitário'), findsOneWidget);

      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
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
}
