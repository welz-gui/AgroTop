import 'dart:convert';
import 'dart:io';

import 'package:agrotop_mobile/api_client.dart';
import 'package:agrotop_mobile/app.dart';
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

MockClient _client() => MockClient((request) async {
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
  return _json({'detail': 'Não encontrado'}, status: 404);
});

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('quatro telas são cobertas nos três modos de tema', (
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

      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
    }
  });
}
