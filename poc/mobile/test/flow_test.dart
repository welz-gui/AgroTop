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

class MemoryTokenStore implements TokenStore {
  String? token;

  @override
  Future<void> clear() async => token = null;

  @override
  Future<String?> read() async => token;

  @override
  Future<void> write(String value) async => token = value;
}

http.Response _json(Object body, {int status = 200}) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('captura login, lista e ficha sem cálculo ou fallback no Dart', (
    tester,
  ) async {
    final captureGoldens = Platform.environment['CAPTURE_GOLDENS'] == '1';
    if (captureGoldens) await loadAppFonts();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    SharedPreferences.setMockInitialValues({});
    final preferences = await SharedPreferences.getInstance();
    final store = MemoryTokenStore();
    final client = MockClient((request) async {
      if (request.method == 'POST' && request.url.path == '/auth/login') {
        final payload = jsonDecode(request.body) as Map<String, dynamic>;
        expect(payload, {'username': 'admin', 'password': 'senha-da-poc'});
        return _json({
          'access_token': 'token-real-da-api-no-fluxo-manual',
          'token_type': 'bearer',
          'expires_in': 28800,
          'user': {
            'id': 1,
            'username': 'admin',
            'name': 'Administrador',
            'role': 'admin',
          },
        });
      }
      expect(
        request.headers['authorization'],
        'Bearer token-real-da-api-no-fluxo-manual',
      );
      if (request.url.path == '/animais') {
        return _json([
          {
            'id': 'BR0001',
            'breed': 'Nelore',
            'sex': 'M',
            'current_weight': 382.4,
            'target_weight': 500.0,
            'lote_id': 'P01',
          },
          {
            'id': 'BR0002',
            'breed': 'Angus',
            'sex': 'F',
            'current_weight': 354.8,
            'target_weight': 490.0,
            'lote_id': 'P02',
          },
        ]);
      }
      if (request.url.path == '/animais/BR0001') {
        return _json({
          'id': 'BR0001',
          'breed': 'Nelore',
          'sex': 'M',
          'current_weight': 382.4,
          'target_weight': 500.0,
          'lote_id': 'P01',
          'lote_name': 'Piquete Central',
          'birth_date': '2024-03-10',
          'entry_date': '2026-01-10',
          'entry_weight': 278.2,
          'gmd_recent_kg_day': 0.742,
          'gmd_total_kg_day': 0.513,
        });
      }
      return _json({'detail': 'Não encontrado'}, status: 404);
    });
    final api = ApiClient(
      tokenStore: store,
      httpClient: client,
      baseUrl: 'http://poc.local',
    );

    await tester.pumpWidget(
      AgroTopApp(preferences: preferences, apiClient: api),
    );
    await tester.pumpAndSettle();
    expect(find.text('Gestão do rebanho'), findsOneWidget);
    if (captureGoldens) {
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('goldens/01-login.png'),
      );
    }

    await tester.enterText(find.byType(TextFormField).at(0), 'admin');
    await tester.enterText(find.byType(TextFormField).at(1), 'senha-da-poc');
    await tester.tap(find.text('Entrar'));
    await tester.pumpAndSettle();
    expect(find.text('BR0001'), findsOneWidget);
    expect(find.text('BR0002'), findsOneWidget);
    if (captureGoldens) {
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('goldens/02-lista.png'),
      );
    }

    await tester.tap(find.text('BR0001'));
    await tester.pumpAndSettle();
    expect(find.text('0.742 kg/dia'), findsOneWidget);
    expect(find.text('GMD calculado no servidor'), findsOneWidget);
    if (captureGoldens) {
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('goldens/03-ficha.png'),
      );
    }
  });
}
